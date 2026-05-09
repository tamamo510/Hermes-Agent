"""kyojuro_search.lib.search_engine — 複数ソースを統合したネット検索エンジン。

DuckDuckGo Instant Answer + Wikipedia (ja/en) を組み合わせて、
温子の問いに対する検索結果を 1 つの SearchResponse に集約する。

設計原則:
- ソースは順番に試す (DuckDuckGo 優先 → Wikipedia)
- どれか 1 つでも取得できれば結果を返す (全失敗時は例外)
- LLM は使わず、結果は機械的に統合
- ネットワークなしテストは HTTP 注入で対応可能
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from .web_search_client import (
    DuckDuckGoClient,
    SearchResponse,
    SearchResult,
    WebSearchError,
    WikipediaClient,
)


@dataclass
class CombinedSearchResponse:
    """複数ソースから集約した検索結果。"""

    query: str
    instant_answer: Optional[str]  # DuckDuckGo の AbstractText (定義等)
    results: list[SearchResult] = field(default_factory=list)
    sources_attempted: list[str] = field(default_factory=list)
    sources_succeeded: list[str] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "instant_answer": self.instant_answer,
            "results": [
                {
                    "title": r.title,
                    "url": r.url,
                    "snippet": r.snippet,
                    "source": r.source,
                }
                for r in self.results
            ],
            "sources_attempted": list(self.sources_attempted),
            "sources_succeeded": list(self.sources_succeeded),
            "errors": dict(self.errors),
        }

    @property
    def message(self) -> str:
        """温子向けの一文にまとめた要約 (敬語)。"""
        if self.instant_answer:
            return f"検索 「{self.query}」: {self.instant_answer}"
        if self.results:
            top = self.results[0]
            return (
                f"検索 「{self.query}」: {top.title} — {top.snippet[:120]}"
                f" ({top.source})"
            )
        if self.errors:
            return f"検索 「{self.query}」: 取得できませんでした ({', '.join(self.errors.keys())})"
        return f"検索 「{self.query}」: 該当なし"


class SearchEngine:
    """複数ソースを統合した検索エンジン。

    Args:
        ddg: DuckDuckGoClient (None なら遅延初期化)
        wiki_ja: WikipediaClient (lang='ja')
        wiki_en: WikipediaClient (lang='en'), None で英語検索無効
    """

    def __init__(
        self,
        ddg: Optional[DuckDuckGoClient] = None,
        wiki_ja: Optional[WikipediaClient] = None,
        wiki_en: Optional[WikipediaClient] = None,
    ) -> None:
        self.ddg = ddg
        self.wiki_ja = wiki_ja
        self.wiki_en = wiki_en

    def _get_ddg(self) -> DuckDuckGoClient:
        if self.ddg is None:
            self.ddg = DuckDuckGoClient()
        return self.ddg

    def _get_wiki_ja(self) -> WikipediaClient:
        if self.wiki_ja is None:
            self.wiki_ja = WikipediaClient(lang="ja")
        return self.wiki_ja

    def _get_wiki_en(self) -> WikipediaClient:
        if self.wiki_en is None:
            self.wiki_en = WikipediaClient(lang="en")
        return self.wiki_en

    def search(
        self,
        query: str,
        max_results_per_source: int = 5,
        use_ddg: bool = True,
        use_wiki_ja: bool = True,
        use_wiki_en: bool = False,
    ) -> CombinedSearchResponse:
        """複数ソースで検索し、結果を統合する。

        Args:
            query: 検索クエリ
            max_results_per_source: 各ソースから取得する最大件数
            use_ddg: DuckDuckGo を使うか
            use_wiki_ja: 日本語 Wikipedia を使うか
            use_wiki_en: 英語 Wikipedia を使うか
        """
        if not query or not query.strip():
            raise WebSearchError("query は空であってはならない")

        result = CombinedSearchResponse(query=query, instant_answer=None)

        if use_ddg:
            result.sources_attempted.append("duckduckgo")
            try:
                ddg_resp = self._get_ddg().search(
                    query, max_results=max_results_per_source
                )
                result.sources_succeeded.append("duckduckgo")
                if ddg_resp.instant_answer:
                    result.instant_answer = ddg_resp.instant_answer
                result.results.extend(ddg_resp.results)
            except WebSearchError as e:
                result.errors["duckduckgo"] = str(e)

        if use_wiki_ja:
            result.sources_attempted.append("wikipedia_ja")
            try:
                wiki_resp = self._get_wiki_ja().search(
                    query, max_results=max_results_per_source
                )
                result.sources_succeeded.append("wikipedia_ja")
                result.results.extend(wiki_resp.results)
            except WebSearchError as e:
                result.errors["wikipedia_ja"] = str(e)

        if use_wiki_en:
            result.sources_attempted.append("wikipedia_en")
            try:
                wiki_resp = self._get_wiki_en().search(
                    query, max_results=max_results_per_source
                )
                result.sources_succeeded.append("wikipedia_en")
                result.results.extend(wiki_resp.results)
            except WebSearchError as e:
                result.errors["wikipedia_en"] = str(e)

        return result
