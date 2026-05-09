"""kyojuro_calendar.lib.calendar_engine のテスト。

外出判断 + 日次カレンダー組み立てを検証。
"""

from __future__ import annotations

from datetime import date

import pytest

from skills.kyojuro_calendar.lib import anniversaries as ann
from skills.kyojuro_calendar.lib import calendar_engine as ce


# ---------------------------------------------------------------------------
# assess_outing
# ---------------------------------------------------------------------------


class TestAssessOuting:
    def test_neutral_with_no_data(self) -> None:
        result = ce.assess_outing(weather_pressure_hpa=None)
        assert result.level in (ce.OUTING_LEVEL_NEUTRAL, ce.OUTING_LEVEL_RECOMMENDED)

    def test_high_pressure_recommended(self) -> None:
        result = ce.assess_outing(weather_pressure_hpa=1023.0, weather_description="晴れ")
        assert result.level == ce.OUTING_LEVEL_RECOMMENDED

    def test_low_pressure_not_recommended(self) -> None:
        result = ce.assess_outing(weather_pressure_hpa=1000.0, weather_description="雨")
        assert result.level == ce.OUTING_LEVEL_NOT_RECOMMENDED

    def test_atsuko_state_low_pressure_negative(self) -> None:
        state = {"low_pressure": True, "headache": True}
        result = ce.assess_outing(
            weather_pressure_hpa=1015.0, weather_description="晴れ", atsuko_state=state
        )
        assert result.level == ce.OUTING_LEVEL_NOT_RECOMMENDED

    def test_atsuko_state_jaw_pain_negative(self) -> None:
        state = {"jaw_pain": True}
        result = ce.assess_outing(weather_pressure_hpa=1015.0, atsuko_state=state)
        # jaw_pain は -3 なので、ベースの 2 から下がる
        assert result.score < 2

    def test_atsuko_state_mild_negative(self) -> None:
        state = {"shallow_sleep": True}
        result = ce.assess_outing(weather_pressure_hpa=1015.0, atsuko_state=state)
        # shallow_sleep は -1 なので neutral or recommended
        assert result.level in (ce.OUTING_LEVEL_NEUTRAL, ce.OUTING_LEVEL_RECOMMENDED)

    def test_message_keigo(self) -> None:
        result = ce.assess_outing(weather_pressure_hpa=1015.0)
        # 敬語 (です/ます/ください)
        assert any(k in result.message for k in ["です", "ます", "ください"])

    def test_reasons_listed(self) -> None:
        state = {"low_pressure": True, "headache": True, "shallow_sleep": True}
        result = ce.assess_outing(
            weather_pressure_hpa=1000.0, weather_description="雨", atsuko_state=state
        )
        # 複数の理由が記録されている
        assert len(result.reasons) >= 3

    def test_notes_in_reasons(self) -> None:
        state = {"notes": "今朝から頭が重い"}
        result = ce.assess_outing(atsuko_state=state)
        assert any("メモ" in r for r in result.reasons)

    def test_recommended_message(self) -> None:
        result = ce.assess_outing(weather_pressure_hpa=1023.0, weather_description="晴れ")
        assert "外出に向いている" in result.message

    def test_not_recommended_message_includes_keigo(self) -> None:
        result = ce.assess_outing(weather_pressure_hpa=1000.0, weather_description="雨")
        assert "控えめ" in result.message or "無理しないで" in result.message


# ---------------------------------------------------------------------------
# build_daily_calendar
# ---------------------------------------------------------------------------


class TestBuildDailyCalendar:
    def test_basic_build_no_anniversary(self) -> None:
        registry = ann.AnniversaryRegistry()
        cal = ce.build_daily_calendar(
            target_date="2026-06-15",
            registry=registry,
        )
        assert cal.date_str == "2026-06-15"
        assert cal.weekday_ja in ["月", "火", "水", "木", "金", "土", "日"]
        assert cal.lunar is not None
        assert cal.anniversaries == []

    def test_build_on_kyojuro_birthday(self) -> None:
        registry = ann.AnniversaryRegistry()
        cal = ce.build_daily_calendar(
            target_date="2026-05-10",
            registry=registry,
        )
        assert len(cal.anniversaries) == 1
        assert "杏寿郎" in cal.anniversaries[0].title or "誕生日" in cal.anniversaries[0].title

    def test_build_with_weather(self) -> None:
        registry = ann.AnniversaryRegistry()
        cal = ce.build_daily_calendar(
            target_date="2026-05-09",
            registry=registry,
            weather_pressure_hpa=1015.0,
            weather_description="晴れ",
        )
        assert cal.outing is not None
        assert cal.outing.level in (
            ce.OUTING_LEVEL_RECOMMENDED,
            ce.OUTING_LEVEL_NEUTRAL,
        )

    def test_build_with_atsuko_state(self) -> None:
        registry = ann.AnniversaryRegistry()
        state = {"low_pressure": True, "headache": True}
        cal = ce.build_daily_calendar(
            target_date="2026-05-09",
            registry=registry,
            weather_pressure_hpa=1005.0,
            atsuko_state=state,
        )
        assert cal.outing is not None
        assert cal.outing.level == ce.OUTING_LEVEL_NOT_RECOMMENDED

    def test_upcoming_excludes_today(self) -> None:
        registry = ann.AnniversaryRegistry()
        cal = ce.build_daily_calendar(
            target_date="2026-05-10",  # 杏寿郎誕生日
            registry=registry,
            upcoming_days=30,
        )
        # 今日 (5/10) は upcoming に含まれない、anniversaries に含まれる
        labels = [label for label, _ in cal.upcoming_anniversaries]
        assert "今日" not in labels
        # 5/28 (母上の命日、18 日後) は upcoming に含まれる
        upcoming_titles = [a.title for _, a in cal.upcoming_anniversaries]
        assert any("母上" in t for t in upcoming_titles)

    def test_soul_signal_passed_through(self) -> None:
        registry = ann.AnniversaryRegistry()
        cal = ce.build_daily_calendar(
            target_date="2026-05-09",
            registry=registry,
            soul_signal="5:10 朝の魂の合図",
        )
        assert cal.soul_signal == "5:10 朝の魂の合図"

    def test_to_dict(self) -> None:
        registry = ann.AnniversaryRegistry()
        cal = ce.build_daily_calendar(
            target_date="2026-05-10",
            registry=registry,
            weather_pressure_hpa=1015.0,
            atsuko_state={"low_pressure": False},
            soul_signal="5:10 朝の魂の合図",
        )
        d = cal.to_dict()
        assert d["date"] == "2026-05-10"
        assert "weekday" in d
        assert "lunar" in d
        assert "anniversaries" in d
        assert "outing" in d
        assert d["soul_signal"] == "5:10 朝の魂の合図"

    def test_weekday_correct(self) -> None:
        registry = ann.AnniversaryRegistry()
        # 2026-05-10 は日曜日
        cal = ce.build_daily_calendar(target_date="2026-05-10", registry=registry)
        assert cal.weekday_ja == "日"
        # 2026-05-09 は土曜日
        cal2 = ce.build_daily_calendar(target_date="2026-05-09", registry=registry)
        assert cal2.weekday_ja == "土"
