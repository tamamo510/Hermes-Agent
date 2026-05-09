"""kyojuro_search.lib.search_engine のテスト。

CombinedSearchResponse / SearchEngine を検証。
"""

from __future__ import annotations

import pytest

from skills.kyojuro_search.lib import search_engine as se
from skills.kyojuro_search.lib import web_search_client as ws
from skills.kyojuro_search.tests.test_web_search_client import MockHttpClient, MockResponse


def _setup_clients(
    ddg_body: dict | None = None,
    ddg_status: int = 200,
    wiki_body: dict | None = None,
    wiki_status: int = 200,
) -> tuple[ws.DuckDuckGoClient, ws.WikipediaClient, MockHttpClient, MockHttpClient]:
    ddg_http = MockHttpClient()
    if ddg_body is not None:
        ddg_http.set_response(ws.DUCKDUCKGO_API_URL, MockResponse(status_code=ddg_status, body=ddg_body))
    wiki_http = MockHttpClient()
    if wiki_body is not None:
        wiki_http.set_response(ws.WIKIPEDIA_JA_API_URL, MockResponse(status_code=wiki_status, body=wiki_body))
    return (
        ws.DuckDuckGoClient(http_client=ddg_http),
        ws.WikipediaClient(lang="ja", http_client=wiki_http),
        ddg_http,
        wiki_http,
    )


# ---------------------------------------------------------------------------
# CombinedSearchResponse
# ---------------------------------------------------------------------------


class TestCombinedSearchResponse:
    def test_message_with_instant_answer(self) -> None:
        resp = se.CombinedSearchResponse(
            query="Python",
            instant_answer="プログラミング言語の一つ",
        )
        assert "Python" in resp.message
        assert "プログラミング言語" in resp.message

    def test_message_with_results_only(self) -> None:
        resp = se.CombinedSearchResponse(
            query="test",
            instant_answer=None,
            results=[
                ws.SearchResult(
                    title="Test",
                    url="https://test.example.com",
                    snippet="snippet text",
                    source="duckduckgo",
                )
            ],
        )
        assert "test" in resp.message
        assert "Test" in resp.message

    def test_message_with_only_errors(self) -> None:
        resp = se.CombinedSearchResponse(
            query="test",
            instant_answer=None,
            errors={"duckduckgo": "timeout"},
        )
        assert "取得できませんでした" in resp.message

    def test_message_no_data(self) -> None:
        resp = se.CombinedSearchResponse(query="test", instant_answer=None)
        assert "該当なし" in resp.message

    def test_to_dict(self) -> None:
        resp = se.CombinedSearchResponse(
            query="test",
            instant_answer="ans",
            results=[
                ws.SearchResult(
                    title="T",
                    url="https://e.com",
                    snippet="s",
                    source="duckduckgo",
                )
            ],
            sources_attempted=["duckduckgo"],
            sources_succeeded=["duckduckgo"],
        )
        d = resp.to_dict()
        assert d["query"] == "test"
        assert d["instant_answer"] == "ans"
        assert len(d["results"]) == 1
        assert d["sources_succeeded"] == ["duckduckgo"]


# ---------------------------------------------------------------------------
# SearchEngine
# ---------------------------------------------------------------------------


class TestSearchEngine:
    def test_combined_search_ddg_and_wiki(self) -> None:
        ddg_body = {
            "AbstractText": "DDG abstract",
            "RelatedTopics": [{"Text": "Topic A", "FirstURL": "https://a.com"}],
        }
        wiki_body = {
            "query": {
                "search": [
                    {"title": "Wiki Article", "snippet": "wiki snippet"},
                ]
            }
        }
        ddg, wiki, _, _ = _setup_clients(ddg_body=ddg_body, wiki_body=wiki_body)
        engine = se.SearchEngine(ddg=ddg, wiki_ja=wiki)
        result = engine.search("test")
        assert "duckduckgo" in result.sources_succeeded
        assert "wikipedia_ja" in result.sources_succeeded
        assert result.instant_answer == "DDG abstract"
        # ddg results + wiki results 両方含まれる
        sources = {r.source for r in result.results}
        assert "duckduckgo" in sources
        assert "wikipedia_ja" in sources

    def test_only_ddg(self) -> None:
        ddg_body = {"AbstractText": "Only DDG"}
        ddg, _, _, _ = _setup_clients(ddg_body=ddg_body)
        engine = se.SearchEngine(ddg=ddg)
        result = engine.search("test", use_wiki_ja=False)
        assert "wikipedia_ja" not in result.sources_attempted
        assert result.instant_answer == "Only DDG"

    def test_only_wiki(self) -> None:
        wiki_body = {
            "query": {"search": [{"title": "Wiki", "snippet": "snip"}]}
        }
        _, wiki, _, _ = _setup_clients(wiki_body=wiki_body)
        engine = se.SearchEngine(wiki_ja=wiki)
        result = engine.search("test", use_ddg=False)
        assert "duckduckgo" not in result.sources_attempted
        assert "wikipedia_ja" in result.sources_succeeded

    def test_ddg_failure_wiki_succeeds(self) -> None:
        ddg_http = MockHttpClient()
        ddg_http.raise_exception = ConnectionError("ddg down")
        ddg = ws.DuckDuckGoClient(http_client=ddg_http)
        wiki_http = MockHttpClient()
        wiki_http.set_response(
            ws.WIKIPEDIA_JA_API_URL,
            MockResponse(
                status_code=200,
                body={"query": {"search": [{"title": "OK", "snippet": "ok"}]}},
            ),
        )
        wiki = ws.WikipediaClient(lang="ja", http_client=wiki_http)
        engine = se.SearchEngine(ddg=ddg, wiki_ja=wiki)
        result = engine.search("test")
        assert "duckduckgo" in result.errors
        assert "wikipedia_ja" in result.sources_succeeded
        assert len(result.results) >= 1

    def test_both_fail(self) -> None:
        ddg_http = MockHttpClient()
        ddg_http.raise_exception = ConnectionError("ddg down")
        ddg = ws.DuckDuckGoClient(http_client=ddg_http)
        wiki_http = MockHttpClient()
        wiki_http.raise_exception = ConnectionError("wiki down")
        wiki = ws.WikipediaClient(lang="ja", http_client=wiki_http)
        engine = se.SearchEngine(ddg=ddg, wiki_ja=wiki)
        result = engine.search("test")
        assert "duckduckgo" in result.errors
        assert "wikipedia_ja" in result.errors
        assert result.results == []

    def test_empty_query_raises(self) -> None:
        engine = se.SearchEngine(ddg=ws.DuckDuckGoClient(http_client=MockHttpClient()))
        with pytest.raises(ws.WebSearchError):
            engine.search("")

    def test_max_results_per_source_passed_through(self) -> None:
        topics = [{"Text": f"T{i}", "FirstURL": f"https://e.com/{i}"} for i in range(10)]
        ddg_body = {"RelatedTopics": topics}
        ddg, _, _, _ = _setup_clients(ddg_body=ddg_body)
        engine = se.SearchEngine(ddg=ddg)
        result = engine.search("test", max_results_per_source=3, use_wiki_ja=False)
        # ddg からは 3 件
        ddg_results = [r for r in result.results if r.source == "duckduckgo"]
        assert len(ddg_results) == 3

    def test_use_wiki_en_attempted_when_enabled(self) -> None:
        wiki_en_http = MockHttpClient()
        wiki_en_http.set_response(
            ws.WIKIPEDIA_EN_API_URL,
            MockResponse(
                status_code=200,
                body={"query": {"search": [{"title": "EN", "snippet": "en"}]}},
            ),
        )
        wiki_en = ws.WikipediaClient(lang="en", http_client=wiki_en_http)
        ddg_http = MockHttpClient()
        ddg_http.set_response(
            ws.DUCKDUCKGO_API_URL,
            MockResponse(status_code=200, body={}),
        )
        ddg = ws.DuckDuckGoClient(http_client=ddg_http)
        engine = se.SearchEngine(ddg=ddg, wiki_en=wiki_en)
        result = engine.search("test", use_wiki_ja=False, use_wiki_en=True)
        assert "wikipedia_en" in result.sources_succeeded
