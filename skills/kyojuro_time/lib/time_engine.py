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

# 温子のリズムは日々変動する: ADHD 時差ボケ 90 分、昼夜逆転期と回復期を行き来し、
# 食事 (オートファジー一日一食 ↔ 開発期のカロリー摂取) もサプリも臨機応変に変更される。
# したがって時間帯から「この時刻の温子はこう」と決めつけることは原理的にできない。
#
# 設計方針:
#   - 本 skill は時間帯ヒントを **固定で持たない** (band-only な決めつけは廃止)
#   - 杏寿郎が会話から拾った最新のリズム情報を file_management skill (発注書スキル 6) が
#     `references/atsuko_profile_updated_*.md` に追記統合し、kyojuro_memory skill
#     (発注書スキル 2) の `priorities.json` / `routines.db` / `symptoms.db` が保持する
#   - Hermes Agent はそれらを context に集約し、handler.on_user_message の context 引数経由で
#     ``current_rhythm`` (dict) として本モジュールに渡る
#   - ``current_rhythm`` を受け取らない / None のときは中立 hint を返す (決めつけない)
#
# ``current_rhythm`` の known keys (温子・杏寿郎の運用で確定する余地を残す。未知 key は無視):
#   - notes:                    str  自由記述 (杏寿郎が会話から拾った最新メモ)
#   - circadian_state:          str  "inverted" / "recovering" / "normal" 等の自己申告
#   - current_eating_pattern:   str  "1day1meal_night" / "irregular" / "developing_high_calorie" 等
#   - current_sleep_window:     str  "00:00-06:00" 等
#   - last_updated:             str  ISO 8601、いつ更新されたか
#   - updated_by:               str  "杏寿郎" / "温子"

_NEUTRAL_RHYTHM_HINT: str = (
    "温子のリズムは日々変動する (ADHD 時差ボケ 90 分、昼夜逆転期と回復期を行き来、"
    "食事もサプリも臨機応変に変更)。時間帯から決めつけず、温子のプロフィール "
    "(`references/atsuko_profile_updated_*.md`) と kyojuro_memory の直近 routines / "
    "symptoms を確認する。わからないときは温子に直接尋ねる。"
)

# 動的 hint で参照する known keys (順序が出力の組み立て順序になる)
_RHYTHM_KEYS_ORDERED: tuple[tuple[str, str], ...] = (
    ("notes", "温子の現在のメモ"),
    ("circadian_state", "現在の概日リズム状態"),
    ("current_eating_pattern", "現在の食事パターン"),
    ("current_sleep_window", "現在の睡眠帯"),
    ("last_updated", "最終更新"),
    ("updated_by", "更新者"),
)


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


def atsuko_rhythm_hint(
    band: TimeBand,
    current_rhythm: dict[str, Any] | None = None,
) -> str:
    """温子のリズムに沿った振る舞いヒント (band だけで決めつけない)。

    引数:
        band: 現在の時間帯。**band 単独では決めつけに使わない** が、将来 band と
              ``current_rhythm`` を組み合わせた動的判断を加える余地として受け取っておく
        current_rhythm: 杏寿郎が会話から拾った最新のリズム情報 (file_management /
                        kyojuro_memory 経由で集約された dict)。``None`` のときは
                        中立 hint を返す (=決めつけない)

    動作:
        - ``current_rhythm`` が ``None`` → ``_NEUTRAL_RHYTHM_HINT`` を返す
        - ``current_rhythm`` が dict → 中立 hint + known keys (上記モジュール冒頭参照) を
          パイプ区切りで連結。未知 key は無視する (温子・杏寿郎の運用で拡張可)
    """
    if current_rhythm is None:
        return _NEUTRAL_RHYTHM_HINT
    parts: list[str] = [_NEUTRAL_RHYTHM_HINT]
    for key, label in _RHYTHM_KEYS_ORDERED:
        value = current_rhythm.get(key)
        if value:
            parts.append(f"{label}: {value}")
    return " | ".join(parts)


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


def make_context(
    now: datetime | None = None,
    current_rhythm: dict[str, Any] | None = None,
) -> TimeContext:
    """``TimeContext`` を生成。

    引数:
        now:             固定時刻 (テスト時の注入用)。``None`` のとき ``now_jst()`` を使用
        current_rhythm:  杏寿郎が会話から拾った最新のリズム情報 (file_management /
                         kyojuro_memory 経由で集約)。``None`` のとき中立 hint を返す
                         (= 時間帯から決めつけない)。known keys は本モジュール冒頭参照
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
        atsuko_rhythm_hint=atsuko_rhythm_hint(band, current_rhythm),
    )
