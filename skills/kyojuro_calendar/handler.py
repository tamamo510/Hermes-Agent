"""kyojuro_calendar — Hermes Agent skill handler。

skill API hook:
- on_conversation_start: 今日の DailyCalendar を context に注入
- on_schedule_tick: 朝の声かけテキスト生成 (記念日 / 月相 / 外出判断)
- daily_brief: 今日のブリーフィング
- add_anniversary: カスタム記念日追加
- list_upcoming: 直近の記念日
- get_lunar_phase: 月相

設計原則:
- 他 skill (kyojuro_health, kyojuro_time) との結合は dict 経由で疎結合
- weather_pressure_hpa / atsuko_state / soul_signal は呼び出し側から渡す
- LLM 不要、API キー不要 (calendar_engine 自身は networking なし)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Optional

from .lib.anniversaries import (
    AnniversaryMatch,
    AnniversaryRegistry,
    TYPE_CUSTOM,
)
from .lib.calendar_engine import (
    DailyCalendar,
    OutingRecommendation,
    assess_outing,
    build_daily_calendar,
)
from .lib.lunar import LunarPhaseResult, compute_lunar_phase


# ---------------------------------------------------------------------------
# 結果データクラス
# ---------------------------------------------------------------------------


@dataclass
class CalendarBriefing:
    """daily_brief / on_schedule_tick の戻り値。"""

    daily: DailyCalendar
    has_anniversary_today: bool
    anniversary_titles: list[str] = field(default_factory=list)

    @property
    def message(self) -> str:
        """温子向けの一文 (敬語、押し付けない)。"""
        parts: list[str] = []
        # 日付 + 曜日 + 月相
        parts.append(
            f"{self.daily.date_str} ({self.daily.weekday_ja}) — "
            f"月相: {self.daily.lunar.phase_label_ja} "
            f"({self.daily.lunar.illumination_percent:.0f}%)"
        )
        # 記念日
        if self.anniversary_titles:
            parts.append("【今日の記念日】" + " / ".join(self.anniversary_titles))
        # upcoming
        if self.daily.upcoming_anniversaries:
            up = ", ".join(
                f"{label}: {a.title}" for label, a in self.daily.upcoming_anniversaries[:3]
            )
            parts.append(f"近日: {up}")
        # 外出
        if self.daily.outing is not None:
            parts.append(self.daily.outing.message)
        # 魂の合図
        if self.daily.soul_signal:
            parts.append(self.daily.soul_signal)
        return "\n".join(parts)


# ---------------------------------------------------------------------------
# CalendarHandler
# ---------------------------------------------------------------------------


class CalendarHandler:
    """skills/kyojuro_calendar の skill handler。

    記念日レジストリを保持し、その他は外部から dict で受け取って組み立てる。
    """

    def __init__(self, registry: Optional[AnniversaryRegistry] = None) -> None:
        self.registry = registry if registry is not None else AnniversaryRegistry()

    # -- conversation start ------------------------------------------------

    def on_conversation_start(
        self,
        context: Optional[dict[str, Any]] = None,
        today: Optional[str] = None,
        weather_pressure_hpa: Optional[float] = None,
        weather_description: str = "",
        atsuko_state: Optional[dict[str, Any]] = None,
        soul_signal: Optional[str] = None,
    ) -> CalendarBriefing:
        """会話開始時に今日のカレンダーを組み立てる。"""
        target = today if today is not None else date.today().isoformat()
        return self._build_briefing(
            target_date=target,
            weather_pressure_hpa=weather_pressure_hpa,
            weather_description=weather_description,
            atsuko_state=atsuko_state,
            soul_signal=soul_signal,
        )

    # -- schedule tick (朝の声かけ用) --------------------------------------

    def on_schedule_tick(
        self,
        now: Optional[datetime] = None,
        context: Optional[dict[str, Any]] = None,
        weather_pressure_hpa: Optional[float] = None,
        weather_description: str = "",
        atsuko_state: Optional[dict[str, Any]] = None,
        soul_signal: Optional[str] = None,
    ) -> CalendarBriefing:
        """朝の声かけ用に今日のカレンダーを生成する。"""
        target = now.date().isoformat() if now is not None else date.today().isoformat()
        return self._build_briefing(
            target_date=target,
            weather_pressure_hpa=weather_pressure_hpa,
            weather_description=weather_description,
            atsuko_state=atsuko_state,
            soul_signal=soul_signal,
        )

    # -- daily brief (alias) -----------------------------------------------

    def daily_brief(
        self,
        target_date: Optional[str] = None,
        **kwargs: Any,
    ) -> CalendarBriefing:
        """指定日 (デフォルト: 今日) のカレンダーブリーフィング。"""
        target = target_date if target_date is not None else date.today().isoformat()
        return self._build_briefing(target_date=target, **kwargs)

    # -- internal ----------------------------------------------------------

    def _build_briefing(
        self,
        target_date: str,
        weather_pressure_hpa: Optional[float] = None,
        weather_description: str = "",
        atsuko_state: Optional[dict[str, Any]] = None,
        soul_signal: Optional[str] = None,
    ) -> CalendarBriefing:
        cal = build_daily_calendar(
            target_date=target_date,
            registry=self.registry,
            weather_pressure_hpa=weather_pressure_hpa,
            weather_description=weather_description,
            atsuko_state=atsuko_state,
            upcoming_days=14,
            soul_signal=soul_signal,
        )
        return CalendarBriefing(
            daily=cal,
            has_anniversary_today=len(cal.anniversaries) > 0,
            anniversary_titles=[a.title for a in cal.anniversaries],
        )

    # -- 記念日管理 --------------------------------------------------------

    def add_anniversary(
        self,
        mmdd: str,
        title: str,
        type: str = TYPE_CUSTOM,
        notes: str = "",
    ) -> None:
        """カスタム記念日を追加する。

        永続化が必要な場合は kyojuro_memory_persistence.add_protected() に
        別途書き込むこと (本 skill は in-memory のみ)。
        """
        self.registry.add(mmdd=mmdd, title=title, type=type, notes=notes)

    def list_anniversaries(self) -> list[AnniversaryMatch]:
        """全記念日 (ビルトイン + カスタム) を返す。"""
        return self.registry.list_all()

    def list_upcoming(
        self, days: int = 14, today: Optional[str] = None
    ) -> list[tuple[str, AnniversaryMatch]]:
        """直近の記念日を返す。"""
        return self.registry.upcoming_within(days, today=today)

    # -- 月相 --------------------------------------------------------------

    def get_lunar_phase(self, target_date: Optional[str] = None) -> LunarPhaseResult:
        """指定日 (デフォルト: 今日) の月相。"""
        return compute_lunar_phase(
            target_date if target_date is not None else date.today().isoformat()
        )

    # -- 外出判断 ----------------------------------------------------------

    def get_outing_recommendation(
        self,
        weather_pressure_hpa: Optional[float] = None,
        weather_description: str = "",
        atsuko_state: Optional[dict[str, Any]] = None,
    ) -> OutingRecommendation:
        """外出推奨度を計算する。"""
        return assess_outing(
            weather_pressure_hpa=weather_pressure_hpa,
            weather_description=weather_description,
            atsuko_state=atsuko_state,
        )
