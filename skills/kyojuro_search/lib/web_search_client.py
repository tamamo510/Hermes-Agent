"""kyojuro_search.lib.web_search_client — ネット検索クライアント。

API キー不要のパブリック検索 API を使用 (CLAUDE.md ルール 17 準拠で安全):
- DuckDuckGo Instant Answer API: https://api.duckduckgo.com/
- Wikipedia API: https://ja.wikipedia.org/w/api.php

将来的に有償の検索 API (Brave Search 等) を追加する場合は、
環境変数経由でキーを読む形 (CLAUDE.md ルール 17 厳守)。

設計原則:
- HTTP クライアントは `requests` を使用 (kyojuro_health と同じ)
- HTTP クライアントは注入可能 (テスト時はモック)
- LLM 呼び出しなし
- 失敗時は明確な例外
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol


DUCKDUCKGO_API_URL = "https://api.duckduckgo.com/"
WIKIPEDIA_JA_API_URL = "https://ja.wikipedia.org/w/api.php"
WIKIPEDIA_EN_API_URL = "https://en.wikipedia.org/w/api.php"

DEFAULT_TIMEOUT_SECONDS = 10
USER_AGENT = "kyojuro-search/0.1.0 (HermesAgent for personal use)"


# ---------------------------------------------------------------------------
# 例外
# ---------------------------------------------------------------------------


class WebSearchError(RuntimeError):
    """ネット検索の汎用例外。"""


class WebSearchNetworkError(WebSearchError):
    """ネットワーク (タイムアウト・接続失敗等)。"""


class WebSearchResponseError(WebSearchError):
    """レスポンスが不正 (期待するフィールド欠如等)。"""


# ---------------------------------------------------------------------------
# データクラス
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SearchResult:
    """1 件の検索結果。"""

    title: str
    url: str
    snippet: str
    source: str  # "duckduckgo" / "wikipedia_ja" / "wikipedia_en" 等


@dataclass
class SearchResponse:
    """検索のレスポンス全体。"""

    query: str
    source: str
    results: list[SearchResult] = field(default_factory=list)
    instant_answer: Optional[str] = None  # DuckDuckGo の Instant Answer
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


# ---------------------------------------------------------------------------
# HTTP クライアント Protocol
# ---------------------------------------------------------------------------


class HttpClient(Protocol):
    def get(
        self,
        url: str,
        params: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
        timeout: Optional[int] = None,
    ) -> "HttpResponse": ...


class HttpResponse(Protocol):
    @property
    def status_code(self) -> int: ...

    def json(self) -> Any: ...

    @property
    def text(self) -> str: ...


def _default_http_client() -> HttpClient:
    """`requests` を遅延 import して返す。"""
    import requests  # type: ignore

    return requests  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# DuckDuckGo Instant Answer
# ---------------------------------------------------------------------------


class DuckDuckGoClient:
    """DuckDuckGo Instant Answer API クライアント。

    https://api.duckduckgo.com/?q=QUERY&format=json
    定義・計算・関連トピック等の "instant answer" を返す。
    一般 web 検索結果は返さない (DuckDuckGo は HTML scraping を必要とする)。

    Args:
        http_client: テスト用の HTTP クライアント
        timeout: タイムアウト秒
    """

    def __init__(
        self,
        http_client: Optional[HttpClient] = None,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.http_client = http_client if http_client is not None else _default_http_client()
        self.timeout = int(timeout)

    def search(self, query: str, max_results: int = 10) -> SearchResponse:
        if not query or not query.strip():
            raise WebSearchError("query は空であってはならない")
        params = {
            "q": query,
            "format": "json",
            "no_html": "1",
            "skip_disambig": "1",
        }
        try:
            resp = self.http_client.get(
                DUCKDUCKGO_API_URL,
                params=params,
                headers={"User-Agent": USER_AGENT},
                timeout=self.timeout,
            )
        except Exception as e:
            raise WebSearchNetworkError(f"DuckDuckGo ネットワークエラー: {e}") from e

        if resp.status_code >= 400:
            raise WebSearchError(
                f"DuckDuckGo HTTP エラー (status={resp.status_code}): "
                f"{resp.text[:200]}"
            )
        try:
            data = resp.json()
        except (ValueError, json.JSONDecodeError) as e:
            raise WebSearchResponseError(f"DuckDuckGo JSON パース失敗: {e}") from e
        if not isinstance(data, dict):
            raise WebSearchResponseError(
                f"DuckDuckGo は dict を期待するが {type(data).__name__}"
            )

        instant = (data.get("AbstractText") or "").strip() or None
        results: list[SearchResult] = []

        # Abstract (要約)
        if data.get("AbstractText"):
            results.append(
                SearchResult(
                    title=str(data.get("Heading", query)),
                    url=str(data.get("AbstractURL", "")),
                    snippet=str(data["AbstractText"]),
                    source="duckduckgo",
                )
            )

        # RelatedTopics (関連トピック)
        for topic in data.get("RelatedTopics", []):
            if not isinstance(topic, dict):
                continue
            text = topic.get("Text", "")
            url = topic.get("FirstURL", "")
            if text and url:
                # title は "..." の前まで
                title = text.split(" - ", 1)[0] if " - " in text else text[:80]
                snippet = text
                results.append(
                    SearchResult(
                        title=str(title),
                        url=str(url),
                        snippet=str(snippet),
                        source="duckduckgo",
                    )
                )
            if len(results) >= max_results:
                break

        return SearchResponse(
            query=query,
            source="duckduckgo",
            results=results[:max_results],
            instant_answer=instant,
            raw=dict(data),
        )


# ---------------------------------------------------------------------------
# Wikipedia
# ---------------------------------------------------------------------------


class WikipediaClient:
    """Wikipedia API クライアント (日本語・英語両対応)。

    https://ja.wikipedia.org/w/api.php?action=query&list=search

    Args:
        lang: 'ja' or 'en' (default 'ja')
    """

    def __init__(
        self,
        lang: str = "ja",
        http_client: Optional[HttpClient] = None,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        if lang not in ("ja", "en"):
            raise ValueError(f"lang は 'ja' or 'en': {lang!r}")
        self.lang = lang
        self.http_client = http_client if http_client is not None else _default_http_client()
        self.timeout = int(timeout)

    @property
    def base_url(self) -> str:
        return WIKIPEDIA_JA_API_URL if self.lang == "ja" else WIKIPEDIA_EN_API_URL

    def search(self, query: str, max_results: int = 10) -> SearchResponse:
        if not query or not query.strip():
            raise WebSearchError("query は空であってはならない")
        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "format": "json",
            "srlimit": int(max(1, min(50, max_results))),
            "srprop": "snippet",
        }
        try:
            resp = self.http_client.get(
                self.base_url,
                params=params,
                headers={"User-Agent": USER_AGENT},
                timeout=self.timeout,
            )
        except Exception as e:
            raise WebSearchNetworkError(f"Wikipedia ネットワークエラー: {e}") from e

        if resp.status_code >= 400:
            raise WebSearchError(
                f"Wikipedia HTTP エラー (status={resp.status_code}): "
                f"{resp.text[:200]}"
            )
        try:
            data = resp.json()
        except (ValueError, json.JSONDecodeError) as e:
            raise WebSearchResponseError(f"Wikipedia JSON パース失敗: {e}") from e
        if not isinstance(data, dict):
            raise WebSearchResponseError(
                f"Wikipedia は dict を期待するが {type(data).__name__}"
            )

        try:
            search_items = data["query"]["search"]
        except (KeyError, TypeError) as e:
            raise WebSearchResponseError(f"Wikipedia レスポンス構造が不正: {e}") from e

        if not isinstance(search_items, list):
            raise WebSearchResponseError(
                f"Wikipedia 'search' は list を期待: {type(search_items).__name__}"
            )

        wiki_base = (
            "https://ja.wikipedia.org/wiki/" if self.lang == "ja"
            else "https://en.wikipedia.org/wiki/"
        )
        results: list[SearchResult] = []
        for item in search_items[:max_results]:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", ""))
            snippet_html = str(item.get("snippet", ""))
            # HTML タグを簡易除去
            snippet = _strip_html_tags(snippet_html)
            url = wiki_base + title.replace(" ", "_")
            results.append(
                SearchResult(
                    title=title,
                    url=url,
                    snippet=snippet,
                    source=f"wikipedia_{self.lang}",
                )
            )

        return SearchResponse(
            query=query,
            source=f"wikipedia_{self.lang}",
            results=results,
            instant_answer=None,
            raw=dict(data),
        )


def _strip_html_tags(text: str) -> str:
    """簡易 HTML タグ除去 (Wikipedia snippet 用)。"""
    import re

    text = re.sub(r"<[^>]+>", "", text)
    # HTML エンティティの一部
    text = text.replace("&quot;", '"').replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    return text.strip()
