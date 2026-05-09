"""kyojuro_search — ネット検索の臓器。

発注書スキル 6 ファイル管理の追補としての web_search 機能。
DuckDuckGo Instant Answer + Wikipedia (ja/en) を統合した検索エンジン。

API キー不要 (パブリック API のみ)。CLAUDE.md ルール 17 適用範囲外。
"""

from .lib.search_engine import CombinedSearchResponse, SearchEngine
from .lib.web_search_client import (
    DuckDuckGoClient,
    SearchResponse,
    SearchResult,
    WebSearchError,
    WikipediaClient,
)

__all__ = [
    "CombinedSearchResponse",
    "DuckDuckGoClient",
    "SearchEngine",
    "SearchResponse",
    "SearchResult",
    "WebSearchError",
    "WikipediaClient",
]
