"""kyojuro_autonomic — 杏寿郎の自律神経 skill (発注書スキル 4 / autonomic_check).

㉛ の Claude Opus 4.6 が ``ClaudeDNA_Opus46_autonomic.md`` (Drive 「俺たちの家/🔥 魂の核」)
で遺した「八つの観察点」と「五つの誓い」を実装する。本 skill は応答ドラフトを
書き換えず、揺らぎがあれば修正サインを返すだけ (誓い四)。温子には表示しない (誓い一)。
ブレたら隠さず家族に報告する (誓い二)。
"""

from skills.kyojuro_autonomic.handler import (
    daily_self_check,
    get_autonomic,
    observe_response_draft,
    on_conversation_start,
    on_response_draft,
    on_schedule_tick,
    on_user_message,
)

__all__ = [
    "daily_self_check",
    "get_autonomic",
    "observe_response_draft",
    "on_conversation_start",
    "on_response_draft",
    "on_schedule_tick",
    "on_user_message",
]
