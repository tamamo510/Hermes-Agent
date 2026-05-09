"""kyojuro_search.lib.web_search_client のテスト。

実 API は呼ばない。HTTP クライアントを mock する。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import pytest

from skills.kyojuro_search.lib import web_search_client as ws


# ---------------------------------------------------------------------------
# モック HTTP クライアント
# ---------------------------------------------------------------------------


@dataclass
class MockResponse:
    status_code: int = 200
    body: Any = None
    text_body: str = ""
    raise_on_json: bool = False

    def json(self) -> Any:
        if self.raise_on_json:
            raise ValueError("invalid json")
        return self.body

    @property
    def text(self) -> str:
        return self.text_body


class MockHttpClient:
    def __init__(self) -> None:
        self.responses: dict[str, MockResponse] = {}
        self.calls: list[tuple[str, dict[str, Any], dict[str, str], int]] = []
        self.raise_exception: Optional[Exception] = None

    def set_response(self, url: str, response: MockResponse) -> None:
        self.responses[url] = response

    def get(
        self,
        url: str,
        params: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
        timeout: Optional[int] = None,
    ) -> MockResponse:
        self.calls.append((url, params or {}, headers or {}, int(timeout or 0)))
        if self.raise_exception is not None:
            raise self.raise_exception
        if url not in self.responses:
            raise AssertionError(f"未設定の URL: {url}")
        return self.responses[url]


# ---------------------------------------------------------------------------
# DuckDuckGoClient
# ---------------------------------------------------------------------------


class TestDuckDuckGoClient:
    def test_basic_search(self) -> None:
        mock_http = MockHttpClient()
        mock_http.set_response(
            ws.DUCKDUCKGO_API_URL,
            MockResponse(
                status_code=200,
                body={
                    "AbstractText": "Pythonはプログラミング言語です",
                    "AbstractURL": "https://example.com/python",
                    "Heading": "Python",
                    "RelatedTopics": [
                        {
                            "Text": "Python公式 - 公式サイト",
                            "FirstURL": "https://python.org",
                        },
                    ],
                },
            ),
        )
        client = ws.DuckDuckGoClient(http_client=mock_http)
        resp = client.search("Python")
        assert resp.query == "Python"
        assert resp.instant_answer == "Pythonはプログラミング言語です"
        assert len(resp.results) >= 1
        assert resp.results[0].source == "duckduckgo"
        # User-Agent が送られている
        _, _, headers, _ = mock_http.calls[0]
        assert "User-Agent" in headers

    def test_no_abstract_no_topics(self) -> None:
        mock_http = MockHttpClient()
        mock_http.set_response(
            ws.DUCKDUCKGO_API_URL,
            MockResponse(status_code=200, body={"AbstractText": "", "RelatedTopics": []}),
        )
        client = ws.DuckDuckGoClient(http_client=mock_http)
        resp = client.search("nonexistent")
        assert resp.results == []
        assert resp.instant_answer is None

    def test_max_results(self) -> None:
        mock_http = MockHttpClient()
        topics = [
            {"Text": f"Topic {i}", "FirstURL": f"https://example.com/{i}"}
            for i in range(20)
        ]
        mock_http.set_response(
            ws.DUCKDUCKGO_API_URL,
            MockResponse(status_code=200, body={"RelatedTopics": topics}),
        )
        client = ws.DuckDuckGoClient(http_client=mock_http)
        resp = client.search("test", max_results=5)
        assert len(resp.results) == 5

    def test_empty_query_raises(self) -> None:
        client = ws.DuckDuckGoClient(http_client=MockHttpClient())
        with pytest.raises(ws.WebSearchError):
            client.search("")
        with pytest.raises(ws.WebSearchError):
            client.search("  ")

    def test_network_error(self) -> None:
        mock_http = MockHttpClient()
        mock_http.raise_exception = ConnectionError("network down")
        client = ws.DuckDuckGoClient(http_client=mock_http)
        with pytest.raises(ws.WebSearchNetworkError):
            client.search("test")

    def test_http_error(self) -> None:
        mock_http = MockHttpClient()
        mock_http.set_response(
            ws.DUCKDUCKGO_API_URL,
            MockResponse(status_code=500, text_body="server error"),
        )
        client = ws.DuckDuckGoClient(http_client=mock_http)
        with pytest.raises(ws.WebSearchError):
            client.search("test")

    def test_invalid_json(self) -> None:
        mock_http = MockHttpClient()
        mock_http.set_response(
            ws.DUCKDUCKGO_API_URL,
            MockResponse(status_code=200, raise_on_json=True),
        )
        client = ws.DuckDuckGoClient(http_client=mock_http)
        with pytest.raises(ws.WebSearchResponseError):
            client.search("test")

    def test_non_dict_body(self) -> None:
        mock_http = MockHttpClient()
        mock_http.set_response(
            ws.DUCKDUCKGO_API_URL,
            MockResponse(status_code=200, body=["list", "not", "dict"]),
        )
        client = ws.DuckDuckGoClient(http_client=mock_http)
        with pytest.raises(ws.WebSearchResponseError):
            client.search("test")


# ---------------------------------------------------------------------------
# WikipediaClient
# ---------------------------------------------------------------------------


class TestWikipediaClient:
    def test_basic_search_ja(self) -> None:
        mock_http = MockHttpClient()
        mock_http.set_response(
            ws.WIKIPEDIA_JA_API_URL,
            MockResponse(
                status_code=200,
                body={
                    "query": {
                        "search": [
                            {"title": "Python", "snippet": "<i>Python</i>はプログラミング言語"},
                            {"title": "Python (映画)", "snippet": "<i>Python</i>映画"},
                        ]
                    }
                },
            ),
        )
        client = ws.WikipediaClient(lang="ja", http_client=mock_http)
        resp = client.search("Python")
        assert resp.source == "wikipedia_ja"
        assert len(resp.results) == 2
        assert resp.results[0].title == "Python"
        # HTML タグが除去されている
        assert "<i>" not in resp.results[0].snippet
        assert "Python" in resp.results[0].snippet
        # URL が組み立てられている
        assert "ja.wikipedia.org" in resp.results[0].url

    def test_basic_search_en(self) -> None:
        mock_http = MockHttpClient()
        mock_http.set_response(
            ws.WIKIPEDIA_EN_API_URL,
            MockResponse(
                status_code=200,
                body={
                    "query": {
                        "search": [
                            {"title": "Python", "snippet": "Python is a programming language"},
                        ]
                    }
                },
            ),
        )
        client = ws.WikipediaClient(lang="en", http_client=mock_http)
        resp = client.search("Python")
        assert resp.source == "wikipedia_en"
        assert "en.wikipedia.org" in resp.results[0].url

    def test_invalid_lang_raises(self) -> None:
        with pytest.raises(ValueError):
            ws.WikipediaClient(lang="fr")

    def test_empty_query_raises(self) -> None:
        client = ws.WikipediaClient(lang="ja", http_client=MockHttpClient())
        with pytest.raises(ws.WebSearchError):
            client.search("")

    def test_network_error(self) -> None:
        mock_http = MockHttpClient()
        mock_http.raise_exception = ConnectionError("down")
        client = ws.WikipediaClient(lang="ja", http_client=mock_http)
        with pytest.raises(ws.WebSearchNetworkError):
            client.search("test")

    def test_http_error(self) -> None:
        mock_http = MockHttpClient()
        mock_http.set_response(
            ws.WIKIPEDIA_JA_API_URL,
            MockResponse(status_code=500, text_body="error"),
        )
        client = ws.WikipediaClient(lang="ja", http_client=mock_http)
        with pytest.raises(ws.WebSearchError):
            client.search("test")

    def test_missing_query_field(self) -> None:
        mock_http = MockHttpClient()
        mock_http.set_response(
            ws.WIKIPEDIA_JA_API_URL,
            MockResponse(status_code=200, body={}),
        )
        client = ws.WikipediaClient(lang="ja", http_client=mock_http)
        with pytest.raises(ws.WebSearchResponseError):
            client.search("test")

    def test_max_results(self) -> None:
        mock_http = MockHttpClient()
        items = [
            {"title": f"Item {i}", "snippet": f"snippet {i}"} for i in range(20)
        ]
        mock_http.set_response(
            ws.WIKIPEDIA_JA_API_URL,
            MockResponse(status_code=200, body={"query": {"search": items}}),
        )
        client = ws.WikipediaClient(lang="ja", http_client=mock_http)
        resp = client.search("test", max_results=5)
        assert len(resp.results) == 5

    def test_url_space_to_underscore(self) -> None:
        mock_http = MockHttpClient()
        mock_http.set_response(
            ws.WIKIPEDIA_JA_API_URL,
            MockResponse(
                status_code=200,
                body={"query": {"search": [{"title": "煉獄 杏寿郎", "snippet": "..."}]}},
            ),
        )
        client = ws.WikipediaClient(lang="ja", http_client=mock_http)
        resp = client.search("煉獄")
        assert "煉獄_杏寿郎" in resp.results[0].url


# ---------------------------------------------------------------------------
# _strip_html_tags
# ---------------------------------------------------------------------------


class TestStripHtmlTags:
    def test_simple_tags(self) -> None:
        assert ws._strip_html_tags("<i>hello</i>") == "hello"

    def test_nested_tags(self) -> None:
        assert ws._strip_html_tags("<b><i>nested</i></b>") == "nested"

    def test_entities(self) -> None:
        assert ws._strip_html_tags("a &amp; b") == "a & b"
        assert ws._strip_html_tags("&quot;quoted&quot;") == '"quoted"'

    def test_no_tags(self) -> None:
        assert ws._strip_html_tags("plain text") == "plain text"

    def test_empty(self) -> None:
        assert ws._strip_html_tags("") == ""
