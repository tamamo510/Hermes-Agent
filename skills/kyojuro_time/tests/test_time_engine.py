"""Unit tests for kyojuro_time.lib.time_engine.

決定性: すべてのテストは固定 datetime を直接渡し、``now_jst()`` は呼ばない
(``test_now_jst_is_aware_jst`` のみ例外)。
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from zoneinfo import ZoneInfo

from skills.kyojuro_time.lib.time_engine import (
    DAWN_SIGNAL_TIME,
    DUSK_SIGNAL_TIME,
    JST,
    SOUL_SIGNAL_WINDOW_MINUTES,
    TimeBand,
    TimeContext,
    atsuko_rhythm_hint,
    band_label_jp,
    band_of,
    format_jp,
    is_soul_signal_exact,
    is_soul_signal_window,
    make_context,
    now_jst,
    soul_signal_kind,
    weekday_en,
    weekday_jp,
)


def _jst(year: int, month: int, day: int, hour: int, minute: int = 0, second: int = 0) -> datetime:
    """テスト用 JST aware datetime ヘルパー。"""
    return datetime(year, month, day, hour, minute, second, tzinfo=JST)


# --- now_jst ----------------------------------------------------------------


def test_now_jst_is_aware_jst() -> None:
    t = now_jst()
    assert t.tzinfo is not None
    assert t.utcoffset() == ZoneInfo("Asia/Tokyo").utcoffset(t)


# --- TimeBand 判定 (境界値テスト) -------------------------------------------


@pytest.mark.parametrize(
    "hour,minute,expected",
    [
        # DEEP_NIGHT: 0:00 - 4:59
        (0, 0, TimeBand.DEEP_NIGHT),
        (3, 33, TimeBand.DEEP_NIGHT),
        (4, 59, TimeBand.DEEP_NIGHT),
        # DAWN: 5:00 - 6:59 (5:10 魂の合図を含む)
        (5, 0, TimeBand.DAWN),
        (5, 10, TimeBand.DAWN),
        (6, 59, TimeBand.DAWN),
        # MORNING: 7:00 - 10:59
        (7, 0, TimeBand.MORNING),
        (10, 59, TimeBand.MORNING),
        # MIDDAY: 11:00 - 14:59
        (11, 0, TimeBand.MIDDAY),
        (14, 59, TimeBand.MIDDAY),
        # AFTERNOON: 15:00 - 17:59 (17:10 魂の合図を含む)
        (15, 0, TimeBand.AFTERNOON),
        (17, 10, TimeBand.AFTERNOON),
        (17, 59, TimeBand.AFTERNOON),
        # EVENING: 18:00 - 20:59
        (18, 0, TimeBand.EVENING),
        (20, 59, TimeBand.EVENING),
        # NIGHT: 21:00 - 23:59
        (21, 0, TimeBand.NIGHT),
        (23, 59, TimeBand.NIGHT),
    ],
)
def test_band_of_boundaries(hour: int, minute: int, expected: TimeBand) -> None:
    assert band_of(_jst(2026, 5, 6, hour, minute)) == expected


def test_band_label_jp_full() -> None:
    """全 7 種類の TimeBand に日本語ラベルが対応する。"""
    expected = {
        TimeBand.DEEP_NIGHT: "深夜",
        TimeBand.DAWN: "夜明け",
        TimeBand.MORNING: "朝",
        TimeBand.MIDDAY: "昼",
        TimeBand.AFTERNOON: "午後",
        TimeBand.EVENING: "夕方",
        TimeBand.NIGHT: "夜",
    }
    for band, label in expected.items():
        assert band_label_jp(band) == label


def test_atsuko_rhythm_hint_all_bands() -> None:
    """全 7 種類でヒントが空でなく、それぞれ異なる文字列であること。"""
    hints = {band: atsuko_rhythm_hint(band) for band in TimeBand}
    assert all(hints[band] for band in TimeBand)
    assert len(set(hints.values())) == len(TimeBand)


# --- 曜日 -------------------------------------------------------------------


def test_weekday_jp_all_days() -> None:
    """2026-05-04 (月) 〜 2026-05-10 (日) の連続 7 日で全曜日を確認。"""
    expected_jp = ["月", "火", "水", "木", "金", "土", "日"]
    expected_en = [
        "Monday", "Tuesday", "Wednesday", "Thursday",
        "Friday", "Saturday", "Sunday",
    ]
    for offset, jp, en in zip(range(7), expected_jp, expected_en):
        t = _jst(2026, 5, 4 + offset, 12, 0)
        assert weekday_jp(t) == jp
        assert weekday_en(t) == en


def test_weekday_kyojuro_birthday_is_sunday() -> None:
    """2026-05-10 = 杏寿郎の誕生日 + 母の日 + 魂入れ日 = 日曜。"""
    t = _jst(2026, 5, 10, 5, 10)
    assert weekday_jp(t) == "日"
    assert weekday_en(t) == "Sunday"


# --- 魂の合図 ---------------------------------------------------------------


@pytest.mark.parametrize(
    "hour,minute,second,exact",
    [
        # 5:10 ピンポイント分 (秒は 0〜59 のいずれか)
        (5, 10, 0, True),
        (5, 10, 30, True),
        (5, 10, 59, True),
        # 17:10 ピンポイント分
        (17, 10, 0, True),
        (17, 10, 59, True),
        # 隣接分は exact ではない
        (5, 9, 59, False),
        (5, 11, 0, False),
        (17, 9, 59, False),
        (17, 11, 0, False),
        # 全く違う時刻
        (12, 0, 0, False),
        (0, 0, 0, False),
    ],
)
def test_is_soul_signal_exact(hour: int, minute: int, second: int, exact: bool) -> None:
    assert is_soul_signal_exact(_jst(2026, 5, 6, hour, minute, second)) is exact


@pytest.mark.parametrize(
    "hour,minute,window",
    [
        # 5:10 ±5 分 (5:05 〜 5:15、両端含む)
        (5, 5, True),
        (5, 7, True),
        (5, 10, True),
        (5, 13, True),
        (5, 15, True),
        # 窓外
        (5, 4, False),
        (5, 16, False),
        # 17:10 ±5 分
        (17, 5, True),
        (17, 10, True),
        (17, 15, True),
        (17, 4, False),
        (17, 16, False),
        # 関係ない時刻
        (12, 0, False),
        (0, 10, False),
    ],
)
def test_is_soul_signal_window(hour: int, minute: int, window: bool) -> None:
    assert is_soul_signal_window(_jst(2026, 5, 6, hour, minute)) is window


def test_soul_signal_kind() -> None:
    assert soul_signal_kind(_jst(2026, 5, 10, 5, 10)) == "dawn_signal"
    assert soul_signal_kind(_jst(2026, 5, 6, 17, 10)) == "dusk_signal"
    # 窓内だがピンポイント分でない場合は None
    assert soul_signal_kind(_jst(2026, 5, 6, 5, 14)) is None
    assert soul_signal_kind(_jst(2026, 5, 6, 17, 11)) is None
    # 窓外は当然 None
    assert soul_signal_kind(_jst(2026, 5, 6, 12, 0)) is None


def test_soul_signal_constants() -> None:
    """定数値が発注書 / SOUL.md と整合していること。"""
    assert DAWN_SIGNAL_TIME.hour == 5 and DAWN_SIGNAL_TIME.minute == 10
    assert DUSK_SIGNAL_TIME.hour == 17 and DUSK_SIGNAL_TIME.minute == 10
    assert SOUL_SIGNAL_WINDOW_MINUTES == 5


# --- aware 強制 -------------------------------------------------------------


def test_band_of_naive_raises() -> None:
    naive = datetime(2026, 5, 6, 12, 0)  # tzinfo なし
    with pytest.raises(ValueError, match="naive datetime"):
        band_of(naive)


def test_make_context_naive_raises() -> None:
    naive = datetime(2026, 5, 6, 12, 0)
    with pytest.raises(ValueError, match="naive datetime"):
        make_context(now=naive)


def test_band_of_utc_is_converted_to_jst() -> None:
    """UTC で 20:10 = JST で 5:10 (翌日)、つまり魂の合図 DAWN になる。"""
    utc_2010 = datetime(2026, 5, 9, 20, 10, tzinfo=timezone.utc)
    assert band_of(utc_2010) == TimeBand.DAWN
    assert is_soul_signal_exact(utc_2010) is True
    assert soul_signal_kind(utc_2010) == "dawn_signal"


# --- format / make_context --------------------------------------------------


def test_format_jp() -> None:
    t = _jst(2026, 5, 10, 5, 10, 0)
    assert format_jp(t) == "2026年05月10日（日）05時10分"


def test_make_context_kyojuro_birthday_signal() -> None:
    """5/10 5:10:00 = 魂入れ日の魂の合図。全フィールドを検証。"""
    t = _jst(2026, 5, 10, 5, 10, 0)
    ctx = make_context(now=t)
    assert isinstance(ctx, TimeContext)
    assert ctx.iso_date == "2026-05-10"
    assert ctx.iso_time == "05:10"
    assert ctx.formatted_jp == "2026年05月10日（日）05時10分"
    assert ctx.weekday_jp == "日"
    assert ctx.weekday_en == "Sunday"
    assert ctx.time_band == "dawn"
    assert ctx.time_band_label_jp == "夜明け"
    assert ctx.is_soul_signal_window is True
    assert ctx.is_soul_signal_exact is True
    assert ctx.soul_signal_kind == "dawn_signal"
    assert "5:10" in ctx.atsuko_rhythm_hint or "深夜活動明け" in ctx.atsuko_rhythm_hint


def test_make_context_to_dict_serializable() -> None:
    """to_dict() が plain dict (JSON serializable) を返す。"""
    import json

    ctx = make_context(now=_jst(2026, 5, 6, 20, 45))
    d = ctx.to_dict()
    assert isinstance(d, dict)
    # JSON 化できる (datetime や Enum を含まない)
    json.dumps(d, ensure_ascii=False)


def test_make_context_default_uses_now_jst() -> None:
    """now=None のとき now_jst() の現在時刻が使われる。"""
    ctx = make_context()
    assert ctx.iso_datetime  # 何かしら値がある
    parsed = datetime.fromisoformat(ctx.iso_datetime)
    assert parsed.tzinfo is not None
