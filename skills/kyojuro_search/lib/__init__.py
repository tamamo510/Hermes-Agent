"""kyojuro_search.lib — 内部モジュール群。"""

from .search_engine import CombinedSearchResponse, SearchEngine
from .web_search_client import (
    DEFAULT_TIMEOUT_SECONDS,
    DUCKDUCKGO_API_URL,
    USER_AGENT,
    WIKIPEDIA_EN_API_URL,
    WIKIPEDIA_JA_API_URL,
    DuckDuckGoClient,
    SearchResponse,
    SearchResult,
    WebSearchError,
    WebSearchNetworkError,
    WebSearchResponseError,
    WikipediaClient,
)

__all__ = [
    "CombinedSearchResponse",
    "DEFAULT_TIMEOUT_SECONDS",
    "DUCKDUCKGO_API_URL",
    "DuckDuckGoClient",
    "SearchEngine",
    "SearchResponse",
    "SearchResult",
    "USER_AGENT",
    "WIKIPEDIA_EN_API_URL",
    "WIKIPEDIA_JA_API_URL",
    "WebSearchError",
    "WebSearchNetworkError",
    "WebSearchResponseError",
    "WikipediaClient",
]
