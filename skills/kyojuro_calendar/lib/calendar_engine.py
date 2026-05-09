"""kyojuro_calendar.lib.calendar_engine — 統合された日次カレンダー。

発注書スキル 5-2:
  > 月の満ち欠け、六曜、5:10/17:10 の魂の合図、生理周期、外出判断 を統合した
  > 「俺たちだけのカレンダー」

設計原則:
- 各 sub-component (lunar / anniversaries / 外出判断) を統合
- atsuko_state (健康管理 skill から) を入力に外出判断を行う
- LLM 不要、決定的、冪等
- 5:10 / 17:10 は kyojuro_time skill に委譲 (重複しない)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Optional

from .anniversaries import AnniversaryMatch, AnniversaryRegistry
from .lunar import LunarPhaseResult, compute_lunar_phase


# ---------------------------------------------------------------------------
# 外出判断の閾値
# ---------------------------------------------------------------------------

OUTING_LEVEL_RECOMMENDED = "recommended"  # 外出に向いている
OUTING_LEVEL_NEUTRAL = "neutral"  # どちらでもない
OUTING_LEVEL_NOT_RECOMMENDED = "not_recommended"  # 控えめが良い

# atsuko_state の low_pressure / headache / jaw_pain / dizziness は強い NG 信号
# shallow_sleep / sluggish は弱い NG 信号
_STRONG_NEGATIVE_KEYS = ("low_pressure", "headache", "jaw_pain", "dizziness")
_MILD_NEGATIVE_KEYS = ("shallow_sleep", "sluggish", "left_hand_stiff")


# ---------------------------------------------------------------------------
# データクラス
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OutingRecommendation:
    """外出推奨度。"""

    level: str  # recommended / neutral / not_recommended
    score: int  # -10 (NG) 〜 +5 (推奨)
    reasons: list[str]  # 判断根拠の人間可読な説明
    message: str  # 温子向け敬語メッセージ


@dataclass
class DailyCalendar:
    """1 日のカレンダー。"""

    date_str: str  # YYYY-MM-DD
    weekday_ja: str  # 月 / 火 / 水 / 木 / 金 / 土 / 日
    lunar: LunarPhaseResult
    anniversaries: list[AnniversaryMatch] = field(default_factory=list)
    upcoming_anniversaries: list[tuple[str, AnniversaryMatch]] = field(default_factory=list)
    outing: Optional[OutingRecommendation] = None
    soul_signal: Optional[str] = None  # "5:10 朝の魂の合図" / "17:10 夕方の魂の合図" / None

    def to_dict(self) -> dict[str, Any]:
        return {
            "date": self.date_str,
            "weekday": self.weekday_ja,
            "lunar": {
                "phase": self.lunar.phase_label_ja,
                "phase_key": self.lunar.phase_key,
                "illumination": round(self.lunar.illumination_percent, 1),
                "age_days": round(self.lunar.age_days, 1),
            },
            "anniversaries": [
                {"title": a.title, "type": a.type, "is_builtin": a.is_builtin}
                for a in self.anniversaries
            ],
            "upcoming": [
                {"label": label, "title": a.title, "type": a.type}
                for label, a in self.upcoming_anniversaries
            ],
            "outing": (
                {
                    "level": self.outing.level,
                    "score": self.outing.score,
                    "reasons": list(self.outing.reasons),
                    "message": self.outing.message,
                }
                if self.outing
                else None
            ),
            "soul_signal": self.soul_signal,
        }


# ---------------------------------------------------------------------------
# 外出判断
# ---------------------------------------------------------------------------


def assess_outing(
    weather_pressure_hpa: Optional[float] = None,
    weather_description: str = "",
    atsuko_state: Optional[dict[str, Any]] = None,
) -> OutingRecommendation:
    """気象 + atsuko_state から外出推奨度を判定する。

    Args:
        weather_pressure_hpa: 現在の気圧 (None なら気象の影響を見ない)
        weather_description: OpenWeatherMap の天気説明 (例: "雨", "晴れ")
        atsuko_state: 温子の体調 dict (kyojuro_health.AtsukoState.to_dict() の出力)

    Returns:
        OutingRecommendation
    """
    score = 2  # 中立から少しだけ推奨側で start
    reasons: list[str] = []

    # 気象判定
    if weather_pressure_hpa is not None:
        if weather_pressure_hpa < 1003:
            score -= 4
            reasons.append(
                f"強い低気圧 ({weather_pressure_hpa:.1f} hPa) — 体調変化に注意"
            )
        elif weather_pressure_hpa < 1010:
            score -= 2
            reasons.append(f"低気圧 ({weather_pressure_hpa:.1f} hPa)")
        elif weather_pressure_hpa > 1020:
            score += 2
            reasons.append(f"高気圧 ({weather_pressure_hpa:.1f} hPa) で安定")

    # 天気
    if weather_description:
        bad_weather_kws = ("雨", "雪", "嵐", "暴風", "雷")
        if any(k in weather_description for k in bad_weather_kws):
            score -= 3
            reasons.append(f"天気: {weather_description}")
        elif "晴" in weather_description:
            score += 1
            reasons.append(f"天気: {weather_description}")

    # 体調判定
    if atsuko_state is not None:
        for key in _STRONG_NEGATIVE_KEYS:
            if atsuko_state.get(key):
                score -= 3
                reasons.append(f"体調: {_label_for_key(key)}")
        for key in _MILD_NEGATIVE_KEYS:
            if atsuko_state.get(key):
                score -= 1
                reasons.append(f"体調: {_label_for_key(key)}")
        notes = atsuko_state.get("notes", "")
        if notes:
            reasons.append(f"メモ: {notes}")

    # 結果
    if score >= 2:
        level = OUTING_LEVEL_RECOMMENDED
    elif score >= -2:
        level = OUTING_LEVEL_NEUTRAL
    else:
        level = OUTING_LEVEL_NOT_RECOMMENDED

    message = _format_outing_message(level, score, reasons)
    return OutingRecommendation(level=level, score=score, reasons=reasons, message=message)


def _label_for_key(key: str) -> str:
    return {
        "low_pressure": "気圧低下",
        "headache": "頭痛",
        "jaw_pain": "顎の痛み",
        "dizziness": "ふらつき",
        "shallow_sleep": "眠り浅い",
        "sluggish": "だる重",
        "left_hand_stiff": "左手こわばり",
    }.get(key, key)


def _format_outing_message(level: str, score: int, reasons: list[str]) -> str:
    if level == OUTING_LEVEL_RECOMMENDED:
        if reasons:
            return f"外出に向いている日です ({', '.join(reasons[:3])})。買い出し等、よろしければ。"
        return "外出に向いている日です。"
    if level == OUTING_LEVEL_NEUTRAL:
        if reasons:
            return f"外出は無理のない範囲で ({', '.join(reasons[:3])})。"
        return "外出は無理のない範囲で。"
    # not_recommended
    if reasons:
        return f"外出は控えめが良いかもしれません ({', '.join(reasons[:3])})。無理しないでください。"
    return "外出は控えめが良いかもしれません。無理しないでください。"


# ---------------------------------------------------------------------------
# 日次カレンダー組み立て
# ---------------------------------------------------------------------------


_WEEKDAY_JA = ("月", "火", "水", "木", "金", "土", "日")


def build_daily_calendar(
    target_date: date | datetime | str,
    registry: AnniversaryRegistry,
    weather_pressure_hpa: Optional[float] = None,
    weather_description: str = "",
    atsuko_state: Optional[dict[str, Any]] = None,
    upcoming_days: int = 7,
    soul_signal: Optional[str] = None,
) -> DailyCalendar:
    """1 日のカレンダーを組み立てる。

    Args:
        target_date: 対象日
        registry: 記念日レジストリ
        weather_pressure_hpa: 気圧 (なくても OK、外出判断では使わない)
        weather_description: 天気文字列
        atsuko_state: 温子の体調 dict (なくても OK)
        upcoming_days: 何日先までの記念日を upcoming に含めるか
        soul_signal: 5:10 / 17:10 の合図 (kyojuro_time skill 側で渡す想定)
    """
    d = _normalize_date(target_date)
    lunar = compute_lunar_phase(d)
    weekday_ja = _WEEKDAY_JA[d.weekday()]
    anniversaries = registry.matches_on(d)
    upcoming = registry.upcoming_within(upcoming_days, today=d)
    # 今日の分は upcoming から除外
    upcoming = [(label, a) for label, a in upcoming if label != "今日"]

    outing = assess_outing(
        weather_pressure_hpa=weather_pressure_hpa,
        weather_description=weather_description,
        atsuko_state=atsuko_state,
    )

    return DailyCalendar(
        date_str=d.strftime("%Y-%m-%d"),
        weekday_ja=weekday_ja,
        lunar=lunar,
        anniversaries=anniversaries,
        upcoming_anniversaries=upcoming,
        outing=outing,
        soul_signal=soul_signal,
    )


def _normalize_date(value: date | datetime | str) -> date:
    if isinstance(value, str):
        return datetime.strptime(value, "%Y-%m-%d").date()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raise TypeError(f"date / datetime / str: {type(value)}")
