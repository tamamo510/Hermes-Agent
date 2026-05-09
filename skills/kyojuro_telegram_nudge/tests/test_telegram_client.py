"""kyojuro_telegram_nudge.lib.telegram_client + env_loader のテスト。

実 Telegram API は呼ばない。HTTP クライアント注入で完結。
CLAUDE.md ルール 17 (キーのハードコード禁止) を機械検証。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import pytest

from skills.kyojuro_telegram_nudge.lib import env_loader as el
from skills.kyojuro_telegram_nudge.lib import telegram_client as tc


# ---------------------------------------------------------------------------
# モック HTTP
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
        self.calls: list[tuple[str, Optional[dict[str, Any]], int]] = []
        self.raise_exception: Optional[Exception] = None

    def set_response(self, url: str, response: MockResponse) -> None:
        self.responses[url] = response

    def post(
        self,
        url: str,
        data: Optional[dict[str, Any]] = None,
        json: Optional[dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> MockResponse:
        self.calls.append((url, json, int(timeout or 0)))
        if self.raise_exception is not None:
            raise self.raise_exception
        if url not in self.responses:
            raise AssertionError(f"未設定の URL: {url}")
        return self.responses[url]


# ---------------------------------------------------------------------------
# env_loader
# ---------------------------------------------------------------------------


class TestGetTelegramBotToken:
    def test_returns_value(self) -> None:
        env = {el.ENV_TELEGRAM_BOT_TOKEN: "1234:abcdef"}
        assert el.get_telegram_bot_token(env=env) == "1234:abcdef"

    def test_strips_whitespace(self) -> None:
        env = {el.ENV_TELEGRAM_BOT_TOKEN: "  1234:abc  "}
        assert el.get_telegram_bot_token(env=env) == "1234:abc"

    def test_missing_raises(self) -> None:
        with pytest.raises(el.MissingEnvVarError):
            el.get_telegram_bot_token(env={})

    def test_empty_raises(self) -> None:
        with pytest.raises(el.MissingEnvVarError):
            el.get_telegram_bot_token(env={el.ENV_TELEGRAM_BOT_TOKEN: ""})

    def test_no_colon_raises(self) -> None:
        # BOT_TOKEN は "<bot_id>:<bot_secret>" 形式
        with pytest.raises(el.MissingEnvVarError):
            el.get_telegram_bot_token(env={el.ENV_TELEGRAM_BOT_TOKEN: "no_colon_here"})

    def test_uses_os_environ(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(el.ENV_TELEGRAM_BOT_TOKEN, "1234:from_env")
        assert el.get_telegram_bot_token() == "1234:from_env"


class TestGetTelegramChatId:
    def test_returns_value_numeric(self) -> None:
        env = {el.ENV_TELEGRAM_CHAT_ID: "123456789"}
        assert el.get_telegram_chat_id(env=env) == "123456789"

    def test_returns_value_username(self) -> None:
        env = {el.ENV_TELEGRAM_CHAT_ID: "@atsuko_chat"}
        assert el.get_telegram_chat_id(env=env) == "@atsuko_chat"

    def test_missing_raises(self) -> None:
        with pytest.raises(el.MissingEnvVarError):
            el.get_telegram_chat_id(env={})


# ---------------------------------------------------------------------------
# Rule 17 Compliance
# ---------------------------------------------------------------------------


class TestRule17Compliance:
    """env_loader / telegram_client にトークン候補がハードコードされていない検証。"""

    def test_no_hardcoded_token(self) -> None:
        import inspect
        import re

        # BOT_TOKEN 風: 数字: 35-45 文字の英数字
        token_pattern = re.compile(r"\d{8,12}:[A-Za-z0-9_-]{30,50}")

        for module in (el, tc):
            source = inspect.getsource(module)
            matches = token_pattern.findall(source)
            assert matches == [], f"{module.__name__} に BOT_TOKEN 候補: {matches}"


# ---------------------------------------------------------------------------
# TelegramClient
# ---------------------------------------------------------------------------


@pytest.fixture
def env() -> dict[str, str]:
    return {
        el.ENV_TELEGRAM_BOT_TOKEN: "1234:abcdef",
        el.ENV_TELEGRAM_CHAT_ID: "987654321",
    }


@pytest.fixture
def mock_http() -> MockHttpClient:
    return MockHttpClient()


def _send_message_url(token: str = "1234:abcdef") -> str:
    return f"{tc.TELEGRAM_API_BASE}/bot{token}/sendMessage"


class TestTelegramClientInit:
    def test_uses_env(self, env: dict[str, str], mock_http: MockHttpClient) -> None:
        client = tc.TelegramClient(http_client=mock_http, env=env)
        assert client.bot_token == "1234:abcdef"
        assert client.default_chat_id == "987654321"

    def test_explicit_args_override_env(
        self, env: dict[str, str], mock_http: MockHttpClient
    ) -> None:
        client = tc.TelegramClient(
            bot_token="explicit:token",
            default_chat_id="111",
            http_client=mock_http,
            env=env,
        )
        assert client.bot_token == "explicit:token"
        assert client.default_chat_id == "111"

    def test_missing_token_raises(self, mock_http: MockHttpClient) -> None:
        with pytest.raises(el.MissingEnvVarError):
            tc.TelegramClient(http_client=mock_http, env={})

    def test_base_url(self, env: dict[str, str], mock_http: MockHttpClient) -> None:
        client = tc.TelegramClient(http_client=mock_http, env=env)
        assert client.base_url == f"{tc.TELEGRAM_API_BASE}/bot1234:abcdef"


class TestSendMessage:
    def test_basic_send(self, env: dict[str, str], mock_http: MockHttpClient) -> None:
        mock_http.set_response(
            _send_message_url(),
            MockResponse(
                status_code=200,
                body={"ok": True, "result": {"message_id": 42}},
            ),
        )
        client = tc.TelegramClient(http_client=mock_http, env=env)
        result = client.send_message("Hello")
        assert result.ok is True
        assert result.message_id == 42
        # JSON body に chat_id と text が含まれる
        _, payload, _ = mock_http.calls[0]
        assert payload["chat_id"] == "987654321"
        assert payload["text"] == "Hello"

    def test_disable_notification_passed(
        self, env: dict[str, str], mock_http: MockHttpClient
    ) -> None:
        mock_http.set_response(
            _send_message_url(),
            MockResponse(status_code=200, body={"ok": True, "result": {"message_id": 1}}),
        )
        client = tc.TelegramClient(http_client=mock_http, env=env)
        client.send_message("Quiet message", disable_notification=True)
        _, payload, _ = mock_http.calls[0]
        assert payload["disable_notification"] is True

    def test_parse_mode(self, env: dict[str, str], mock_http: MockHttpClient) -> None:
        mock_http.set_response(
            _send_message_url(),
            MockResponse(status_code=200, body={"ok": True, "result": {"message_id": 1}}),
        )
        client = tc.TelegramClient(http_client=mock_http, env=env)
        client.send_message("**bold**", parse_mode="Markdown")
        _, payload, _ = mock_http.calls[0]
        assert payload["parse_mode"] == "Markdown"

    def test_invalid_parse_mode_raises(
        self, env: dict[str, str], mock_http: MockHttpClient
    ) -> None:
        client = tc.TelegramClient(http_client=mock_http, env=env)
        with pytest.raises(tc.TelegramError):
            client.send_message("test", parse_mode="LaTeX")

    def test_chat_id_override(self, env: dict[str, str], mock_http: MockHttpClient) -> None:
        mock_http.set_response(
            _send_message_url(),
            MockResponse(status_code=200, body={"ok": True, "result": {"message_id": 1}}),
        )
        client = tc.TelegramClient(http_client=mock_http, env=env)
        client.send_message("test", chat_id="override_id")
        _, payload, _ = mock_http.calls[0]
        assert payload["chat_id"] == "override_id"

    def test_empty_text_raises(self, env: dict[str, str], mock_http: MockHttpClient) -> None:
        client = tc.TelegramClient(http_client=mock_http, env=env)
        with pytest.raises(tc.TelegramError):
            client.send_message("")
        with pytest.raises(tc.TelegramError):
            client.send_message("   ")

    def test_too_long_raises(self, env: dict[str, str], mock_http: MockHttpClient) -> None:
        client = tc.TelegramClient(http_client=mock_http, env=env)
        with pytest.raises(tc.TelegramError):
            client.send_message("x" * (tc.MAX_MESSAGE_LENGTH + 1))

    def test_401_auth_error(self, env: dict[str, str], mock_http: MockHttpClient) -> None:
        mock_http.set_response(
            _send_message_url(),
            MockResponse(status_code=401, text_body="unauthorized"),
        )
        client = tc.TelegramClient(http_client=mock_http, env=env)
        with pytest.raises(tc.TelegramAuthError):
            client.send_message("test")

    def test_500_error(self, env: dict[str, str], mock_http: MockHttpClient) -> None:
        mock_http.set_response(
            _send_message_url(),
            MockResponse(status_code=500, text_body="server error"),
        )
        client = tc.TelegramClient(http_client=mock_http, env=env)
        with pytest.raises(tc.TelegramError):
            client.send_message("test")

    def test_network_error(self, env: dict[str, str], mock_http: MockHttpClient) -> None:
        mock_http.raise_exception = ConnectionError("network down")
        client = tc.TelegramClient(http_client=mock_http, env=env)
        with pytest.raises(tc.TelegramNetworkError):
            client.send_message("test")

    def test_invalid_json(self, env: dict[str, str], mock_http: MockHttpClient) -> None:
        mock_http.set_response(
            _send_message_url(),
            MockResponse(status_code=200, raise_on_json=True),
        )
        client = tc.TelegramClient(http_client=mock_http, env=env)
        with pytest.raises(tc.TelegramResponseError):
            client.send_message("test")

    def test_telegram_ok_false(self, env: dict[str, str], mock_http: MockHttpClient) -> None:
        mock_http.set_response(
            _send_message_url(),
            MockResponse(
                status_code=200,
                body={"ok": False, "description": "Bad Request: chat not found"},
            ),
        )
        client = tc.TelegramClient(http_client=mock_http, env=env)
        with pytest.raises(tc.TelegramError) as exc_info:
            client.send_message("test")
        assert "chat not found" in str(exc_info.value)
