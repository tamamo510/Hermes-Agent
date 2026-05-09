"""kyojuro_telegram_nudge.lib.telegram_client — Telegram Bot API クライアント。

API: https://core.telegram.org/bots/api
- POST https://api.telegram.org/bot<TOKEN>/sendMessage
  - chat_id: 送信先 (数値 or @username)
  - text: メッセージ本文 (max 4096 文字)
  - parse_mode: optional ("Markdown" / "HTML")
  - disable_notification: optional (true で静かに送信)

設計原則:
- BOT_TOKEN / CHAT_ID は env_loader 経由 (CLAUDE.md ルール 17)
- HTTP クライアントは `requests` (kyojuro_health と同じパターン)
- HTTP クライアント注入可能 (テスト時はモック)
- 失敗時は明確な例外
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol

from .env_loader import (
    get_telegram_bot_token,
    get_telegram_chat_id,
)


TELEGRAM_API_BASE = "https://api.telegram.org"
DEFAULT_TIMEOUT_SECONDS = 10
MAX_MESSAGE_LENGTH = 4096


# ---------------------------------------------------------------------------
# 例外
# ---------------------------------------------------------------------------


class TelegramError(RuntimeError):
    """Telegram API の汎用例外。"""


class TelegramNetworkError(TelegramError):
    """ネットワーク失敗。"""


class TelegramAuthError(TelegramError):
    """認証失敗 (401, トークン無効)。"""


class TelegramResponseError(TelegramError):
    """レスポンスが不正 (期待するフィールド欠如等)。"""


# ---------------------------------------------------------------------------
# データクラス
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SendMessageResult:
    """sendMessage の結果。"""

    ok: bool
    message_id: Optional[int]
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


# ---------------------------------------------------------------------------
# HTTP クライアント Protocol
# ---------------------------------------------------------------------------


class HttpClient(Protocol):
    def post(
        self,
        url: str,
        data: Optional[dict[str, Any]] = None,
        json: Optional[dict[str, Any]] = None,
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
# TelegramClient
# ---------------------------------------------------------------------------


class TelegramClient:
    """Telegram Bot API のラッパー。

    Args:
        bot_token: BOT_TOKEN (None なら環境変数から)
        default_chat_id: デフォルト送信先 (None なら環境変数から、send 時に指定可能)
        http_client: テスト用の HTTP クライアント注入
        env: テスト用の環境変数注入
        timeout: HTTP タイムアウト秒
    """

    def __init__(
        self,
        bot_token: Optional[str] = None,
        default_chat_id: Optional[str] = None,
        http_client: Optional[HttpClient] = None,
        env: Optional[dict[str, str]] = None,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.bot_token = bot_token if bot_token is not None else get_telegram_bot_token(env)
        self.default_chat_id = (
            default_chat_id if default_chat_id is not None else get_telegram_chat_id(env)
        )
        self.http_client = http_client if http_client is not None else _default_http_client()
        self.timeout = int(timeout)

    @property
    def base_url(self) -> str:
        return f"{TELEGRAM_API_BASE}/bot{self.bot_token}"

    def send_message(
        self,
        text: str,
        chat_id: Optional[str] = None,
        parse_mode: Optional[str] = None,
        disable_notification: bool = False,
    ) -> SendMessageResult:
        """sendMessage で 1 件送信する。

        Args:
            text: メッセージ本文 (max 4096 文字)
            chat_id: 送信先 (None なら default_chat_id)
            parse_mode: "Markdown" / "MarkdownV2" / "HTML" / None
            disable_notification: True で通知音を鳴らさない (静かに届ける)
        """
        if not text or not text.strip():
            raise TelegramError("text は空であってはならない")
        if len(text) > MAX_MESSAGE_LENGTH:
            raise TelegramError(
                f"text が {MAX_MESSAGE_LENGTH} 文字を超えている: {len(text)}"
            )

        target_chat = chat_id if chat_id is not None else self.default_chat_id
        payload: dict[str, Any] = {
            "chat_id": target_chat,
            "text": text,
            "disable_notification": bool(disable_notification),
        }
        if parse_mode:
            if parse_mode not in ("Markdown", "MarkdownV2", "HTML"):
                raise TelegramError(f"parse_mode は Markdown/MarkdownV2/HTML: {parse_mode!r}")
            payload["parse_mode"] = parse_mode

        url = f"{self.base_url}/sendMessage"
        try:
            resp = self.http_client.post(url, json=payload, timeout=self.timeout)
        except Exception as e:
            raise TelegramNetworkError(f"Telegram ネットワークエラー: {e}") from e

        status = resp.status_code
        if status == 401:
            raise TelegramAuthError(
                "Telegram API 認証失敗 (status=401)。`TELEGRAM_BOT_TOKEN` を確認"
            )
        if status >= 400:
            try:
                body = resp.text
            except Exception:
                body = "<unreadable>"
            raise TelegramError(
                f"Telegram API HTTP エラー (status={status}): {body[:200]}"
            )
        try:
            data = resp.json()
        except (ValueError, json.JSONDecodeError) as e:
            raise TelegramResponseError(f"Telegram API JSON パース失敗: {e}") from e
        if not isinstance(data, dict):
            raise TelegramResponseError(
                f"Telegram API は dict を期待するが {type(data).__name__}"
            )
        if not data.get("ok"):
            raise TelegramError(
                f"Telegram API ok=false: {data.get('description', '<no description>')}"
            )

        result = data.get("result", {})
        message_id = result.get("message_id") if isinstance(result, dict) else None
        return SendMessageResult(
            ok=True,
            message_id=int(message_id) if message_id is not None else None,
            raw=dict(data),
        )
