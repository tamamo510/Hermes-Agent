"""kyojuro_calendar — カレンダーの臓器。

発注書スキル 5「カレンダー管理 (calendar_manager)」の実装。
記念日 / 月相 / 外出判断 を統合した「俺たちだけのカレンダー」。
"""

from .lib.anniversaries import (
    BUILTIN_ANNIVERSARIES,
    AnniversaryMatch,
    AnniversaryRegistry,
)
from .lib.calendar_engine import (
    DailyCalendar,
    OutingRecommendation,
    assess_outing,
    build_daily_calendar,
)
from .lib.lunar import (
    LunarPhaseResult,
    compute_lunar_phase,
    is_full_moon,
    is_new_moon,
)

__all__ = [
    "BUILTIN_ANNIVERSARIES",
    "AnniversaryMatch",
    "AnniversaryRegistry",
    "DailyCalendar",
    "LunarPhaseResult",
    "OutingRecommendation",
    "assess_outing",
    "build_daily_calendar",
    "compute_lunar_phase",
    "is_full_moon",
    "is_new_moon",
]
