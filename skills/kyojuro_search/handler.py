"""kyojuro_search — Hermes Agent skill handler。

skill API hook:
- on_user_message: 「検索」「調べて」keyword を検出して自動検索
- search: 明示的な検索 (杏寿郎 / 温子からの直接呼び出し)
- search_wikipedia_only: Wikipedia 限定検索

設計原則:
- ネット接続が前提だが、失敗時はクリアに伝える
- LLM 不要 (規則ベース keyword 検出 + パブリック API)
- API キー不要 (DuckDuckGo Instant Answer + Wikipedia)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional

from .lib.search_engine import CombinedSearchResponse, SearchEngine
from .lib.web_search_client import WebSearchError


# ---------------------------------------------------------------------------
# 検索 keyword 抽出パターン
# ---------------------------------------------------------------------------

# 「Xを検索」「Xって何?」「Xについて調べて」等
# 注意: より specific な pattern を先に置く (greedy minimum 対策)
_SEARCH_TRIGGER_PATTERNS = (
    re.compile(r"(.+?)について(教えて|調べて)"),
    re.compile(r"(.+?)とは\??"),
    re.compile(r"(.+?)って(何|なに)\??"),
    re.compile(r"(.+?)を?(検索|調べて|教えて|何だっけ)"),
)


def detect_search_query(message: str) -> Optional[str]:
    """温子の発言から検索クエリを抽出する。

    マッチしなければ None。
    """
    if not message or not message.strip():
        return None
    msg = message.strip()
    for pattern in _SEARCH_TRIGGER_PATTERNS:
        m = pattern.search(msg)
        if m:
            query = m.group(1).strip()
            # 一般的な接続語を除去
            for prefix in ["これ", "それ", "あれ", "今", "ねえ", "ねぇ"]:
                if query.startswith(prefix):
                    query = query[len(prefix):].strip()
            if query:
                return query
    return None


# ---------------------------------------------------------------------------
# 結果データクラス
# ---------------------------------------------------------------------------


@dataclass
class UserMessageSearchResult:
    triggered: bool
    detected_query: Optional[str] = None
    response: Optional[CombinedSearchResponse] = None
    error: Optional[str] = None

    @property
    def message(self) -> str:
        if not self.triggered:
            return ""
        if self.error:
            return f"検索失敗: {self.error}"
        if self.response:
            return self.response.message
        return ""


# ---------------------------------------------------------------------------
# SearchHandler
# ---------------------------------------------------------------------------


class SearchHandler:
    """skills/kyojuro_search の skill handler。"""

    def __init__(self, engine: Optional[SearchEngine] = None) -> None:
        self.engine = engine if engine is not None else SearchEngine()

    # -- user message ------------------------------------------------------

    def on_user_message(
        self,
        message: str,
        context: Optional[dict[str, Any]] = None,
        max_results_per_source: int = 5,
    ) -> UserMessageSearchResult:
        """温子の発言から検索 keyword を検出して、自動で検索する。

        トリガーがなければ recorded=False で返す。
        """
        query = detect_search_query(message)
        if query is None:
            return UserMessageSearchResult(triggered=False)

        try:
            response = self.engine.search(
                query, max_results_per_source=max_results_per_source
            )
            return UserMessageSearchResult(
                triggered=True,
                detected_query=query,
                response=response,
            )
        except WebSearchError as e:
            return UserMessageSearchResult(
                triggered=True,
                detected_query=query,
                error=str(e),
            )

    # -- 明示的な検索 -------------------------------------------------------

    def search(
        self,
        query: str,
        max_results_per_source: int = 5,
        use_ddg: bool = True,
        use_wiki_ja: bool = True,
        use_wiki_en: bool = False,
    ) -> CombinedSearchResponse:
        """杏寿郎・温子からの明示的な検索リクエスト。"""
        return self.engine.search(
            query=query,
            max_results_per_source=max_results_per_source,
            use_ddg=use_ddg,
            use_wiki_ja=use_wiki_ja,
            use_wiki_en=use_wiki_en,
        )

    def search_wikipedia_only(
        self,
        query: str,
        lang: str = "ja",
        max_results: int = 5,
    ) -> CombinedSearchResponse:
        """Wikipedia 限定検索 (信頼できる情報源のみ欲しい時)。"""
        if lang not in ("ja", "en"):
            raise ValueError(f"lang は 'ja' or 'en': {lang!r}")
        if lang == "ja":
            return self.engine.search(
                query=query,
                max_results_per_source=max_results,
                use_ddg=False,
                use_wiki_ja=True,
                use_wiki_en=False,
            )
        return self.engine.search(
            query=query,
            max_results_per_source=max_results,
            use_ddg=False,
            use_wiki_ja=False,
            use_wiki_en=True,
        )
