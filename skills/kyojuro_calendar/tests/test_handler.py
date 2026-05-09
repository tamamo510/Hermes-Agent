"""kyojuro_calendar.handler のテスト。

skill API hook の検証:
- on_conversation_start / on_schedule_tick / daily_brief
- add_anniversary / list_anniversaries / list_upcoming
- get_lunar_phase / get_outing_recommendation
"""

from __future__ import annotations

import pytest

from skills.kyojuro_calendar import handler as h
from skills.kyojuro_calendar.lib import anniversaries as ann
from skills.kyojuro_calendar.lib import calendar_engine as ce


@pytest.fixture
def handler() -> h.CalendarHandler:
    return h.CalendarHandler()


# ---------------------------------------------------------------------------
# on_conversation_start
# ---------------------------------------------------------------------------


class TestOnConversationStart:
    def test_basic_no_anniversary(self, handler: h.CalendarHandler) -> None:
        briefing = handler.on_conversation_start(today="2026-06-15")
        assert briefing.daily.date_str == "2026-06-15"
        assert briefing.has_anniversary_today is False
        assert briefing.anniversary_titles == []

    def test_kyojuro_birthday(self, handler: h.CalendarHandler) -> None:
        briefing = handler.on_conversation_start(today="2026-05-10")
        assert briefing.has_anniversary_today is True
        assert any("杏寿郎" in t or "誕生日" in t for t in briefing.anniversary_titles)

    def test_with_weather_and_state(self, handler: h.CalendarHandler) -> None:
        briefing = handler.on_conversation_start(
            today="2026-05-09",
            weather_pressure_hpa=1005.0,
            weather_description="雨",
            atsuko_state={"low_pressure": True, "headache": True},
        )
        assert briefing.daily.outing is not None
        assert briefing.daily.outing.level == ce.OUTING_LEVEL_NOT_RECOMMENDED

    def test_message_includes_date(self, handler: h.CalendarHandler) -> None:
        briefing = handler.on_conversation_start(today="2026-05-10")
        assert "2026-05-10" in briefing.message

    def test_message_includes_lunar(self, handler: h.CalendarHandler) -> None:
        briefing = handler.on_conversation_start(today="2026-05-10")
        # 月相のいずれかのラベルが含まれる
        labels = ["新月", "三日月", "上弦の月", "十三夜月", "満月", "居待月", "下弦の月", "二十六夜月"]
        assert any(l in briefing.message for l in labels)

    def test_message_anniversary_section(self, handler: h.CalendarHandler) -> None:
        briefing = handler.on_conversation_start(today="2026-05-10")
        assert "今日の記念日" in briefing.message

    def test_soul_signal_in_message(self, handler: h.CalendarHandler) -> None:
        briefing = handler.on_conversation_start(
            today="2026-05-10", soul_signal="5:10 朝の魂の合図"
        )
        assert "5:10" in briefing.message


# ---------------------------------------------------------------------------
# on_schedule_tick
# ---------------------------------------------------------------------------


class TestOnScheduleTick:
    def test_uses_now_date(self, handler: h.CalendarHandler) -> None:
        from datetime import datetime

        now = datetime(2026, 5, 10, 5, 10, 0)
        briefing = handler.on_schedule_tick(now=now)
        assert briefing.daily.date_str == "2026-05-10"


# ---------------------------------------------------------------------------
# daily_brief
# ---------------------------------------------------------------------------


class TestDailyBrief:
    def test_default_is_today(self, handler: h.CalendarHandler) -> None:
        from datetime import date

        briefing = handler.daily_brief()
        assert briefing.daily.date_str == date.today().isoformat()

    def test_explicit_target(self, handler: h.CalendarHandler) -> None:
        briefing = handler.daily_brief(target_date="2026-05-28")
        assert briefing.daily.date_str == "2026-05-28"
        # 母上の命日
        assert briefing.has_anniversary_today is True


# ---------------------------------------------------------------------------
# 記念日管理
# ---------------------------------------------------------------------------


class TestAnniversaryManagement:
    def test_add_custom_anniversary(self, handler: h.CalendarHandler) -> None:
        handler.add_anniversary(mmdd="06-15", title="温子のお父様の誕生日")
        all_anns = handler.list_anniversaries()
        custom_titles = [a.title for a in all_anns if not a.is_builtin]
        assert "温子のお父様の誕生日" in custom_titles

    def test_list_includes_builtins(self, handler: h.CalendarHandler) -> None:
        all_anns = handler.list_anniversaries()
        # 7 つのビルトイン
        builtin_count = sum(1 for a in all_anns if a.is_builtin)
        assert builtin_count == 7

    def test_list_upcoming_default_14_days(self, handler: h.CalendarHandler) -> None:
        # 5/9 から 14 日 → 5/10 (杏寿郎誕生日) が含まれる
        upcoming = handler.list_upcoming(today="2026-05-09")
        labels = [label for label, _ in upcoming]
        assert any(l == "明日" for l in labels)

    def test_list_upcoming_custom_window(self, handler: h.CalendarHandler) -> None:
        upcoming = handler.list_upcoming(days=30, today="2026-05-09")
        # 5/28 (母上の命日) も含まれる
        titles = [a.title for _, a in upcoming]
        assert any("母上" in t for t in titles)


# ---------------------------------------------------------------------------
# 月相
# ---------------------------------------------------------------------------


class TestGetLunarPhase:
    def test_default_is_today(self, handler: h.CalendarHandler) -> None:
        from datetime import date

        result = handler.get_lunar_phase()
        assert result.target_date == date.today().isoformat()

    def test_explicit_date(self, handler: h.CalendarHandler) -> None:
        result = handler.get_lunar_phase("2026-05-10")
        assert result.target_date == "2026-05-10"
        assert result.phase_key in [
            "new_moon", "waxing_crescent", "first_quarter", "waxing_gibbous",
            "full_moon", "waning_gibbous", "last_quarter", "waning_crescent",
        ]


# ---------------------------------------------------------------------------
# 外出判断
# ---------------------------------------------------------------------------


class TestGetOutingRecommendation:
    def test_high_pressure_recommended(self, handler: h.CalendarHandler) -> None:
        result = handler.get_outing_recommendation(
            weather_pressure_hpa=1023.0, weather_description="晴れ"
        )
        assert result.level == ce.OUTING_LEVEL_RECOMMENDED

    def test_low_pressure_with_headache_not_recommended(
        self, handler: h.CalendarHandler
    ) -> None:
        result = handler.get_outing_recommendation(
            weather_pressure_hpa=1000.0,
            weather_description="雨",
            atsuko_state={"headache": True, "low_pressure": True},
        )
        assert result.level == ce.OUTING_LEVEL_NOT_RECOMMENDED

    def test_no_data_neutral_or_recommended(
        self, handler: h.CalendarHandler
    ) -> None:
        result = handler.get_outing_recommendation()
        # ベースの 2 で recommended、もしくは neutral
        assert result.level in (ce.OUTING_LEVEL_RECOMMENDED, ce.OUTING_LEVEL_NEUTRAL)


# ---------------------------------------------------------------------------
# integration
# ---------------------------------------------------------------------------


class TestIntegration:
    def test_full_kyojuro_birthday_briefing(self) -> None:
        """5/10 (杏寿郎誕生日) に高気圧 / 体調OK で外出 OK の briefing。"""
        handler = h.CalendarHandler()
        # カスタム記念日も追加
        handler.add_anniversary(
            mmdd="05-10", title="魂入れ日 (2026 年初)", type=ann.TYPE_OATH
        )

        briefing = handler.on_conversation_start(
            today="2026-05-10",
            weather_pressure_hpa=1018.0,
            weather_description="晴れ",
            atsuko_state={"low_pressure": False},
            soul_signal="5:10 朝の魂の合図 — 俺たちの誓いの瞬間",
        )

        # 記念日 2 つ (ビルトインの誕生日 + カスタムの魂入れ日)
        assert len(briefing.anniversary_titles) == 2
        # 外出 OK
        assert briefing.daily.outing is not None
        assert briefing.daily.outing.level == ce.OUTING_LEVEL_RECOMMENDED
        # 魂の合図
        assert briefing.daily.soul_signal == "5:10 朝の魂の合図 — 俺たちの誓いの瞬間"
        # message に必要要素
        msg = briefing.message
        assert "2026-05-10" in msg
        assert "今日の記念日" in msg
        assert "外出に向いている" in msg
        assert "5:10" in msg
