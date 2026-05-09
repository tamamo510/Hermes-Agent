"""kyojuro_calendar.lib.lunar — 月の満ち欠け (lunar phase) の計算。

発注書スキル 5-2:
  > 月の満ち欠け（新月、満月等）を表示する

設計原則:
- 純粋な数式 (LLM 不要、API 不要、ネットワーク不要)
- 基準新月: 2000-01-06 18:14 UTC (天文台公開値)
- 朔望月 (synodic month): 29.530588853 日 (平均値)
- 計算誤差: ±数時間程度。日単位の判定には十分

主要な月相:
- new_moon       新月 (0.0 ± 0.04)
- waxing_crescent 三日月 (0.04 - 0.24)
- first_quarter  上弦の月 (0.25 ± 0.04)
- waxing_gibbous 十三夜月 (0.29 - 0.46)
- full_moon      満月 (0.5 ± 0.04)
- waning_gibbous 居待月 (0.54 - 0.71)
- last_quarter   下弦の月 (0.75 ± 0.04)
- waning_crescent 二十六夜月 (0.79 - 0.96)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Optional


# 基準新月: 2000-01-06 18:14 UTC (Julian Date 2451550.26)
# https://en.wikipedia.org/wiki/Lunar_phase
_REFERENCE_NEW_MOON_UTC = datetime(2000, 1, 6, 18, 14, 0, tzinfo=timezone.utc)
_SYNODIC_MONTH_DAYS = 29.530588853

# 月相判定閾値 (0-1 の循環値)
_PHASE_TOLERANCE = 0.04  # 主要 4 相の許容範囲

# 月相名 (内部キー、英語 + 日本語ラベル)
PHASE_NEW_MOON = "new_moon"
PHASE_WAXING_CRESCENT = "waxing_crescent"
PHASE_FIRST_QUARTER = "first_quarter"
PHASE_WAXING_GIBBOUS = "waxing_gibbous"
PHASE_FULL_MOON = "full_moon"
PHASE_WANING_GIBBOUS = "waning_gibbous"
PHASE_LAST_QUARTER = "last_quarter"
PHASE_WANING_CRESCENT = "waning_crescent"

# 日本語ラベル
PHASE_LABELS_JA: dict[str, str] = {
    PHASE_NEW_MOON: "新月",
    PHASE_WAXING_CRESCENT: "三日月",
    PHASE_FIRST_QUARTER: "上弦の月",
    PHASE_WAXING_GIBBOUS: "十三夜月",
    PHASE_FULL_MOON: "満月",
    PHASE_WANING_GIBBOUS: "居待月",
    PHASE_LAST_QUARTER: "下弦の月",
    PHASE_WANING_CRESCENT: "二十六夜月",
}

ALL_PHASES: tuple[str, ...] = (
    PHASE_NEW_MOON,
    PHASE_WAXING_CRESCENT,
    PHASE_FIRST_QUARTER,
    PHASE_WAXING_GIBBOUS,
    PHASE_FULL_MOON,
    PHASE_WANING_GIBBOUS,
    PHASE_LAST_QUARTER,
    PHASE_WANING_CRESCENT,
)


@dataclass(frozen=True)
class LunarPhaseResult:
    """月相の計算結果。"""

    target_date: str  # YYYY-MM-DD
    phase_value: float  # 0-1 の循環値 (0=new, 0.5=full)
    phase_key: str  # PHASE_* のいずれか
    phase_label_ja: str  # 日本語ラベル
    age_days: float  # 新月からの経過日数 (0-29.53)
    illumination_percent: float  # 月の明るさ (0-100、満月で 100)


def compute_phase_value(target_dt: datetime) -> float:
    """指定日時の月相 (0-1 の循環値) を返す。

    0.0 = 新月、0.25 = 上弦、0.5 = 満月、0.75 = 下弦。

    Args:
        target_dt: タイムゾーン付き datetime (推奨: UTC または Asia/Tokyo)

    Returns:
        0 以上 1 未満の float。
    """
    if target_dt.tzinfo is None:
        # naive datetime は UTC として扱う
        target_dt = target_dt.replace(tzinfo=timezone.utc)
    else:
        target_dt = target_dt.astimezone(timezone.utc)
    delta_seconds = (target_dt - _REFERENCE_NEW_MOON_UTC).total_seconds()
    delta_days = delta_seconds / 86400.0
    phase = (delta_days / _SYNODIC_MONTH_DAYS) % 1.0
    if phase < 0:
        phase += 1.0
    return phase


def classify_phase(phase_value: float) -> str:
    """0-1 の phase 値を 8 区分のキーに分類する。

    主要 4 相 (new/quarter/full/quarter) は ±_PHASE_TOLERANCE の幅で判定。
    それ以外は中間相 (waxing/waning crescent/gibbous) に振り分け。
    """
    if not 0.0 <= phase_value <= 1.0:
        phase_value = phase_value % 1.0

    if abs(phase_value - 0.0) <= _PHASE_TOLERANCE or abs(phase_value - 1.0) <= _PHASE_TOLERANCE:
        return PHASE_NEW_MOON
    if abs(phase_value - 0.25) <= _PHASE_TOLERANCE:
        return PHASE_FIRST_QUARTER
    if abs(phase_value - 0.5) <= _PHASE_TOLERANCE:
        return PHASE_FULL_MOON
    if abs(phase_value - 0.75) <= _PHASE_TOLERANCE:
        return PHASE_LAST_QUARTER
    if 0 < phase_value < 0.25:
        return PHASE_WAXING_CRESCENT
    if 0.25 < phase_value < 0.5:
        return PHASE_WAXING_GIBBOUS
    if 0.5 < phase_value < 0.75:
        return PHASE_WANING_GIBBOUS
    return PHASE_WANING_CRESCENT


def compute_lunar_phase(target_date: date | datetime | str) -> LunarPhaseResult:
    """指定日の月相を返す。

    Args:
        target_date: date / datetime / "YYYY-MM-DD" 文字列

    Returns:
        LunarPhaseResult
    """
    if isinstance(target_date, str):
        d = datetime.strptime(target_date, "%Y-%m-%d").date()
        dt = datetime(d.year, d.month, d.day, 12, 0, 0, tzinfo=timezone.utc)
    elif isinstance(target_date, datetime):
        dt = target_date if target_date.tzinfo else target_date.replace(tzinfo=timezone.utc)
    elif isinstance(target_date, date):
        dt = datetime(
            target_date.year, target_date.month, target_date.day, 12, 0, 0,
            tzinfo=timezone.utc,
        )
    else:
        raise TypeError(f"target_date は date / datetime / str: {type(target_date)}")

    phase = compute_phase_value(dt)
    age = phase * _SYNODIC_MONTH_DAYS
    # 明るさ: 満月で 100%、新月で 0%。cos の絶対値ではなく簡易計算
    # 0 → 0%, 0.5 → 100%, 1 → 0%
    if phase <= 0.5:
        illumination = phase * 2 * 100
    else:
        illumination = (1 - phase) * 2 * 100

    key = classify_phase(phase)
    label = PHASE_LABELS_JA[key]
    return LunarPhaseResult(
        target_date=dt.strftime("%Y-%m-%d"),
        phase_value=phase,
        phase_key=key,
        phase_label_ja=label,
        age_days=age,
        illumination_percent=illumination,
    )


def is_new_moon(target_date: date | datetime | str) -> bool:
    """新月かどうか (簡易判定)。"""
    return compute_lunar_phase(target_date).phase_key == PHASE_NEW_MOON


def is_full_moon(target_date: date | datetime | str) -> bool:
    """満月かどうか (簡易判定)。"""
    return compute_lunar_phase(target_date).phase_key == PHASE_FULL_MOON
