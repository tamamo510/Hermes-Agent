"""kyojuro_search.handler のテスト。

実 API は呼ばない。SearchEngine を mock 化された clients で構築する。
"""

from __future__ import annotations

import pytest

from skills.kyojuro_search import handler as h
from skills.kyojuro_search.lib import search_engine as se
from skills.kyojuro_search.lib import web_search_client as ws
from skills.kyojuro_search.tests.test_web_search_client import MockHttpClient, MockResponse


# ---------------------------------------------------------------------------
# detect_search_query
# ---------------------------------------------------------------------------


class TestDetectSearchQuery:
    def test_kensaku(self) -> None:
        assert h.detect_search_query("Pythonを検索") == "Python"

    def test_shirabete(self) -> None:
        assert h.detect_search_query("Pythonを調べて") == "Python"

    def test_oshiete(self) -> None:
        assert h.detect_search_query("Pythonを教えて") == "Python"

    def test_xtte_nani(self) -> None:
        assert h.detect_search_query("Pythonって何?") == "Python"

    def test_xtoha(self) -> None:
        assert h.detect_search_query("Pythonとは?") == "Python"

    def test_x_ni_tsuite(self) -> None:
        assert h.detect_search_query("Pythonについて教えて") == "Python"

    def test_empty_returns_none(self) -> None:
        assert h.detect_search_query("") is None
        assert h.detect_search_query("  ") is None

    def test_no_trigger_returns_none(self) -> None:
        assert h.detect_search_query("こんにちは") is None
        assert h.detect_search_query("ご飯食べた") is None

    def test_strips_filler_prefixes(self) -> None:
        assert h.detect_search_query("これって何?") in ("?", None) or h.detect_search_query("これって何?") == ""
        # "ねえ Python って何?" → "Python"
        result = h.detect_search_query("ねえPythonって何?")
        assert result == "Python"


# ---------------------------------------------------------------------------
# SearchHandler
# ---------------------------------------------------------------------------


def _make_handler_with_mock(
    ddg_body: dict | None = None,
    wiki_body: dict | None = None,
    ddg_raise: Exception | None = None,
) -> h.SearchHandler:
    ddg_http = MockHttpClient()
    if ddg_raise is not None:
        ddg_http.raise_exception = ddg_raise
    elif ddg_body is not None:
        ddg_http.set_response(
            ws.DUCKDUCKGO_API_URL,
            MockResponse(status_code=200, body=ddg_body),
        )
    wiki_http = MockHttpClient()
    if wiki_body is not None:
        wiki_http.set_response(
            ws.WIKIPEDIA_JA_API_URL,
            MockResponse(status_code=200, body=wiki_body),
        )
    ddg = ws.DuckDuckGoClient(http_client=ddg_http)
    wiki = ws.WikipediaClient(lang="ja", http_client=wiki_http)
    engine = se.SearchEngine(ddg=ddg, wiki_ja=wiki)
    return h.SearchHandler(engine=engine)


class TestOnUserMessage:
    def test_triggers_on_kensaku(self) -> None:
        handler = _make_handler_with_mock(
            ddg_body={"AbstractText": "Python is a programming language"},
            wiki_body={"query": {"search": [{"title": "Python", "snippet": "snip"}]}},
        )
        result = handler.on_user_message("Pythonを検索")
        assert result.triggered is True
        assert result.detected_query == "Python"
        assert result.response is not None

    def test_no_trigger_returns_false(self) -> None:
        handler = _make_handler_with_mock()
        result = handler.on_user_message("こんにちは")
        assert result.triggered is False

    def test_search_failure_returns_error(self) -> None:
        handler = _make_handler_with_mock(ddg_raise=ConnectionError("network"))
        wiki_http = MockHttpClient()
        wiki_http.raise_exception = ConnectionError("wiki down")
        wiki = ws.WikipediaClient(lang="ja", http_client=wiki_http)
        # 全ソース失敗
        engine = se.SearchEngine(
            ddg=ws.DuckDuckGoClient(http_client=MockHttpClient()),
            wiki_ja=wiki,
        )
        # ddg は default (URL 未設定で AssertionError → catch されない)
        # 別途ちゃんとした失敗パターンを作る
        ddg_http = MockHttpClient()
        ddg_http.raise_exception = ConnectionError("ddg down")
        engine.ddg = ws.DuckDuckGoClient(http_client=ddg_http)
        handler = h.SearchHandler(engine=engine)
        result = handler.on_user_message("Pythonを検索")
        # トリガーは true だが、両ソース失敗で response 中に errors が入る
        assert result.triggered is True
        # response の errors に項目あり (例外は engine 内でキャッチされるので、
        # handler は error attr ではなく response 経由で渡る)
        assert result.response is not None
        assert len(result.response.errors) > 0

    def test_message_property_with_response(self) -> None:
        handler = _make_handler_with_mock(
            ddg_body={"AbstractText": "Test answer"},
            wiki_body={"query": {"search": []}},
        )
        result = handler.on_user_message("Pythonって何?")
        assert "Test answer" in result.message


class TestSearch:
    def test_basic_search(self) -> None:
        handler = _make_handler_with_mock(
            ddg_body={"AbstractText": "abstract"},
            wiki_body={"query": {"search": [{"title": "T", "snippet": "s"}]}},
        )
        resp = handler.search("test")
        assert resp.instant_answer == "abstract"

    def test_search_wikipedia_only_ja(self) -> None:
        handler = _make_handler_with_mock(
            wiki_body={"query": {"search": [{"title": "Wiki", "snippet": "wiki snip"}]}},
        )
        resp = handler.search_wikipedia_only("test", lang="ja")
        assert "duckduckgo" not in resp.sources_attempted
        assert "wikipedia_ja" in resp.sources_succeeded

    def test_search_wikipedia_only_en(self) -> None:
        ddg_http = MockHttpClient()
        wiki_en_http = MockHttpClient()
        wiki_en_http.set_response(
            ws.WIKIPEDIA_EN_API_URL,
            MockResponse(
                status_code=200,
                body={"query": {"search": [{"title": "EN", "snippet": "en snip"}]}},
            ),
        )
        ddg = ws.DuckDuckGoClient(http_client=ddg_http)
        wiki_ja = ws.WikipediaClient(lang="ja", http_client=MockHttpClient())
        wiki_en = ws.WikipediaClient(lang="en", http_client=wiki_en_http)
        engine = se.SearchEngine(ddg=ddg, wiki_ja=wiki_ja, wiki_en=wiki_en)
        handler = h.SearchHandler(engine=engine)
        resp = handler.search_wikipedia_only("test", lang="en")
        assert "wikipedia_en" in resp.sources_succeeded

    def test_invalid_lang_raises(self) -> None:
        handler = _make_handler_with_mock()
        with pytest.raises(ValueError):
            handler.search_wikipedia_only("test", lang="fr")
