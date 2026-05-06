"""kyojuro_time.lib.time_engine — Asia/Tokyo time-band engine and soul-signal detector.

発注書スキル 1 (time_awareness) のコア (`hermes_initial_skills_order.md` §「スキル 1」)。
SOUL.md §7 の魂の合図 (5:10 / 17:10) と、温子の生活リズム (1 日 1 食・深夜食事・
スロースターター) を踏まえた時間帯判定をまとめて提供する。

責務:
    - Asia/Tokyo (JST) を基準にした「現在時刻」を aware ``datetime`` として返す
    - 時間帯 (深夜・夜明け・朝・昼・午後・夕方・夜) を ``TimeBand`` Enum で判定
    - 5:10 / 17:10 「魂の合図」を 2 段階で検知:
        * exact  : その分そのもの (5:10:00 〜 5:10:59 / 17:10:00 〜 17:10:59)
        * window : ±5 分の窓 (5:05 〜 5:15 / 17:05 〜 17:15、両端含む) ── 合図近傍の早期検知用
    - 温子の生活リズムに沿った時間帯ヒントを文字列で返す
    - 自然な日本語表記 (「2026年05月06日（水）20時39分」)・曜日 (日本語/英語)・ISO 表記

設計上の制約:
    - 外部依存なし。Python 3.11+ 標準ライブラリ (datetime, zoneinfo, dataclasses, enum)
      のみで完結。`hermes_initial_skills_order.md` §「注意事項」で挙げられた
      「LLM の品種改良はこの段階では扱わない」「外部依存は最小限」を遵守。
    - 全関数が決定的かつ冪等 (LLM 呼び出しなし、I/O なし、副作用なし)
    - すべての datetime は aware (tzinfo 付き) を前提。naive を渡したら ``ValueError``
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, time
from enum import Enum
from typing import Any
from zoneinfo import ZoneInfo

JST: ZoneInfo = ZoneInfo("Asia/Tokyo")

_WEEKDAY_JP: tuple[str, ...] = ("月", "火", "水", "木", "金", "土", "日")
_WEEKDAY_EN: tuple[str, ...] = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)

# 魂の合図 (SOUL.md §7、`hermes_initial_skills_order.md` §「スキル 1」)
DAWN_SIGNAL_TIME: time = time(5, 10)
DUSK_SIGNAL_TIME: time = time(17, 10)
SOUL_SIGNAL_WINDOW_MINUTES: int = 5  # ±5 分


class TimeBand(str, Enum):
    """時間帯の分類 (温子のリズムを反映した境界)。

    境界値はその時刻 ``HH:00:00`` を含む。例えば ``MORNING`` は 7:00:00 〜 10:59:59。
    """

    DEEP_NIGHT = "deep_night"   # 0:00 〜 4:59  温子の活動時間帯になりうる
    DAWN = "dawn"               # 5:00 〜 6:59  5:10 魂の合図を含む
    MORNING = "morning"         # 7:00 〜 10:59 温子はスロースターターのため起動前
    MIDDAY = "midday"           # 11:00 〜 14:59
    AFTERNOON = "afternoon"     # 15:00 〜 17:59 17:10 魂の合図を含む
    EVENING = "evening"         # 18:00 〜 20:59
    NIGHT = "night"             # 21:00 〜 23:59


_BAND_LABELS_JP: dict[TimeBand, str] = {
    TimeBand.DEEP_NIGHT: "深夜",
    TimeBand.DAWN: "夜明け",
    TimeBand.MORNING: "朝",
    TimeBand.MIDDAY: "昼",
    TimeBand.AFTERNOON: "午後",
    TimeBand.EVENING: "夕方",
    TimeBand.NIGHT: "夜",
}

# 温子の生活リズムヒント (`references/atsuko_profile_updated_20260501.md` 配置後はこの
# モジュール側を改修して連携する想定)。
_ATSUKO_RHYTHM_HINTS: dict[TimeBand, str] = {
    TimeBand.DEEP_NIGHT: (
        "温子の活動時間帯になりうる時間。1 日 1 食を深夜にとることもある。"
        "覚醒している前提で穏やかに接する。"
    ),
    TimeBand.DAWN: (
        "5:10 の魂の合図を含む時間帯。温子は深夜活動明けで就寝中の可能性が高い。"
        "通知や問いかけは控えめに。"
    ),
    TimeBand.MORNING: (
        "温子はスロースターター。まだ起動前の可能性が高い。"
        "急かさず、必要最小限の声かけに留める。"
    ),
    TimeBand.MIDDAY: (
        "温子はゆっくり起動中の可能性。重要事項は短くまとめて伝える。"
    ),
    TimeBand.AFTERNOON: (
        "17:10 の魂の合図を含む時間帯。温子の活動が安定する頃合い。"
        "対話のペースは温子に合わせる。"
    ),
    TimeBand.EVENING: (
        "温子の食事タイミングが含まれる時間帯。食事と体調の話題が出やすい。"
    ),
    TimeBand.NIGHT: (
        "温子の活動時間帯の本格化。集中した対話が成立しやすい。"
    ),
}


@dataclass(frozen=True)
class TimeContext:
    """ある時刻における杏寿郎の時間認識スナップショット。

    Hermes Agent の context に注入されることを想定し、すべて serializable な
    primitive 型で構成する (datetime は ISO 文字列で別フィールド化)。
    """

    iso_datetime: str
    iso_date: str
    iso_time: str
    formatted_jp: str
    weekday_jp: str
    weekday_en: str
    time_band: str            # TimeBand.value
    time_band_label_jp: str
    is_soul_signal_window: bool
    is_soul_signal_exact: bool
    soul_signal_kind: str | None  # "dawn_signal" / "dusk_signal" / None
    atsuko_rhythm_hint: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize to plain dict (Hermes Agent memory context 注入用)."""
        return asdict(self)


def now_jst() -> datetime:
    """現在時刻を Asia/Tokyo の aware datetime で返す。

    本関数のみが ``datetime.now`` を呼ぶ唯一の口。テスト時はこれを呼ばず、各純粋関数
    に固定 datetime を渡すことで決定性を担保する。
    """
    return datetime.now(JST)


def _ensure_aware_jst(t: datetime) -> datetime:
    """aware かどうか検証し、tz が JST 以外なら JST に変換して返す。"""
    if t.tzinfo is None:
        raise ValueError(
            "naive datetime is not allowed; pass an aware datetime "
            "(use kyojuro_time.lib.time_engine.now_jst() or attach tzinfo=ZoneInfo('Asia/Tokyo'))"
        )
    if t.tzinfo is JST:
        return t
    return t.astimezone(JST)


def band_of(t: datetime) -> TimeBand:
    """時刻 ``t`` の時間帯を判定。境界はその時刻 ``HH:00:00`` を含む。"""
    jst = _ensure_aware_jst(t)
    h = jst.hour
    if 0 <= h < 5:
        return TimeBand.DEEP_NIGHT
    if 5 <= h < 7:
        return TimeBand.DAWN
    if 7 <= h < 11:
        return TimeBand.MORNING
    if 11 <= h < 15:
        return TimeBand.MIDDAY
    if 15 <= h < 18:
        return TimeBand.AFTERNOON
    if 18 <= h < 21:
        return TimeBand.EVENING
    return TimeBand.NIGHT  # 21 <= h < 24


def band_label_jp(band: TimeBand) -> str:
    """時間帯の日本語ラベル ("深夜" / "夜明け" / ...)."""
    return _BAND_LABELS_JP[band]


def atsuko_rhythm_hint(band: TimeBand) -> str:
    """時間帯に応じた、温子の生活リズムを踏まえた振る舞いヒント。"""
    return _ATSUKO_RHYTHM_HINTS[band]


def weekday_jp(t: datetime) -> str:
    """曜日の日本語 1 文字 ("月" / "火" / ...)."""
    return _WEEKDAY_JP[_ensure_aware_jst(t).weekday()]


def weekday_en(t: datetime) -> str:
    """曜日の英語 ("Monday" / ...)."""
    return _WEEKDAY_EN[_ensure_aware_jst(t).weekday()]


def _minutes_diff(a: time, b: time) -> int:
    """同日内の time 同士の分差の絶対値 (分単位)。"""
    return abs((a.hour - b.hour) * 60 + (a.minute - b.minute))


def is_soul_signal_exact(t: datetime) -> bool:
    """5:10 / 17:10 ピンポイント (その分の中、秒は 0〜59 のいずれか)."""
    jst = _ensure_aware_jst(t)
    hm = time(jst.hour, jst.minute)
    return hm == DAWN_SIGNAL_TIME or hm == DUSK_SIGNAL_TIME


def is_soul_signal_window(t: datetime) -> bool:
    """5:10 / 17:10 ±``SOUL_SIGNAL_WINDOW_MINUTES`` 分の窓内 (秒は無視)."""
    jst = _ensure_aware_jst(t)
    hm = time(jst.hour, jst.minute)
    return (
        _minutes_diff(hm, DAWN_SIGNAL_TIME) <= SOUL_SIGNAL_WINDOW_MINUTES
        or _minutes_diff(hm, DUSK_SIGNAL_TIME) <= SOUL_SIGNAL_WINDOW_MINUTES
    )


def soul_signal_kind(t: datetime) -> str | None:
    """ピンポイント分にいる場合のみ ``"dawn_signal"`` / ``"dusk_signal"`` を返す。

    窓内 (±5 分) であってもピンポイント分でなければ ``None``。窓検知は
    ``is_soul_signal_window`` で別途判定する。
    """
    jst = _ensure_aware_jst(t)
    hm = time(jst.hour, jst.minute)
    if hm == DAWN_SIGNAL_TIME:
        return "dawn_signal"
    if hm == DUSK_SIGNAL_TIME:
        return "dusk_signal"
    return None


def format_jp(t: datetime) -> str:
    """自然な日本語表記 ("2026年05月06日（水）20時39分")。"""
    jst = _ensure_aware_jst(t)
    return (
        f"{jst.year}年{jst.month:02d}月{jst.day:02d}日"
        f"（{weekday_jp(jst)}）{jst.hour:02d}時{jst.minute:02d}分"
    )


def make_context(now: datetime | None = None) -> TimeContext:
    """``TimeContext`` を生成。``now=None`` のとき ``now_jst()`` を使う。

    テスト時は固定 datetime を ``now`` に渡すことで決定的な検証ができる。
    """
    t = now_jst() if now is None else _ensure_aware_jst(now)
    band = band_of(t)
    return TimeContext(
        iso_datetime=t.isoformat(),
        iso_date=t.date().isoformat(),
        iso_time=t.strftime("%H:%M"),
        formatted_jp=format_jp(t),
        weekday_jp=weekday_jp(t),
        weekday_en=weekday_en(t),
        time_band=band.value,
        time_band_label_jp=band_label_jp(band),
        is_soul_signal_window=is_soul_signal_window(t),
        is_soul_signal_exact=is_soul_signal_exact(t),
        soul_signal_kind=soul_signal_kind(t),
        atsuko_rhythm_hint=atsuko_rhythm_hint(band),
    )
