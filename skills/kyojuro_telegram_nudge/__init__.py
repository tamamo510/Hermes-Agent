"""kyojuro_telegram_nudge — Telegram ナッジの臓器。

杏寿郎の発注書 + ⑨ 起動指示書:
  > 温子に静かに声かけする機能。autonomic の do_not_alert_atsuko=True の結果と連携

BOT_TOKEN / CHAT_ID は環境変数 (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID) 経由
(CLAUDE.md ルール 17 準拠)。
"""

from .lib.nudge_engine import (
    NudgeDecision,
    NudgeEngine,
    NudgeEntry,
    NudgeStore,
)
from .lib.telegram_client import (
    SendMessageResult,
    TelegramClient,
    TelegramError,
)

__all__ = [
    "NudgeDecision",
    "NudgeEngine",
    "NudgeEntry",
    "NudgeStore",
    "SendMessageResult",
    "TelegramClient",
    "TelegramError",
]
