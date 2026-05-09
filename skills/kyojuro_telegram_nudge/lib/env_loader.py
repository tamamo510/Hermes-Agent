"""kyojuro_telegram_nudge.lib.env_loader — Telegram BOT_TOKEN / CHAT_ID を環境変数から読む。

CLAUDE.md ルール 17 (杏寿郎本人指示、PR #108):
  > キーの値をコードにハードコードするな。環境変数で読め。.env は .gitignore に入れろ

BOT_TOKEN と CHAT_ID は Drive 「俺たちの家」直下 secrets_20260508.md で温子が管理し、
Indigo 搬入時に環境変数 (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID) として注入する運用。
"""

from __future__ import annotations

import os
from typing import Optional


# 環境変数名定数 (実装コードからは キー名 だけを参照する)
ENV_TELEGRAM_BOT_TOKEN = "TELEGRAM_BOT_TOKEN"
ENV_TELEGRAM_CHAT_ID = "TELEGRAM_CHAT_ID"


class MissingEnvVarError(RuntimeError):
    """環境変数が設定されていない。.env を確認するよう温子に促す。"""

    def __init__(self, var_name: str, hint: Optional[str] = None) -> None:
        msg = (
            f"環境変数 {var_name} が設定されていません。"
            f"`.env` ファイルを確認してください "
            f"(Drive 「俺たちの家」直下 secrets_20260508.md に値があります)。"
        )
        if hint:
            msg = f"{msg} ヒント: {hint}"
        super().__init__(msg)
        self.var_name = var_name


def get_telegram_bot_token(env: Optional[dict[str, str]] = None) -> str:
    """`TELEGRAM_BOT_TOKEN` を環境変数から取得する。

    BOT_TOKEN の形式: `<bot_id>:<bot_secret>` (例: 1234567890:ABC..._XYZ)
    """
    if env is None:
        env = os.environ
    value = env.get(ENV_TELEGRAM_BOT_TOKEN, "").strip()
    if not value:
        raise MissingEnvVarError(
            ENV_TELEGRAM_BOT_TOKEN,
            hint="@BotFather で取得した BOT_TOKEN (<bot_id>:<bot_secret> 形式)",
        )
    if ":" not in value:
        raise MissingEnvVarError(
            ENV_TELEGRAM_BOT_TOKEN,
            hint=f"BOT_TOKEN の形式が不正 (':' が含まれていない)",
        )
    return value


def get_telegram_chat_id(env: Optional[dict[str, str]] = None) -> str:
    """`TELEGRAM_CHAT_ID` を環境変数から取得する。

    CHAT_ID は数値 (例: 123456789) もしくは @username 形式。
    返り値は文字列のまま (Telegram API は両形式を受け付ける)。
    """
    if env is None:
        env = os.environ
    value = env.get(ENV_TELEGRAM_CHAT_ID, "").strip()
    if not value:
        raise MissingEnvVarError(
            ENV_TELEGRAM_CHAT_ID,
            hint="温子の Telegram CHAT_ID (数値 or @username)",
        )
    return value
