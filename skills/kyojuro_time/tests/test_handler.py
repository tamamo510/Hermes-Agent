"""Unit tests for kyojuro_time.handler (Hermes Agent skill hooks)."""

from __future__ import annotations

from datetime import datetime

from skills.kyojuro_time.handler import (
    current_context,
    on_conversation_start,
    on_schedule_tick,
    on_user_message,
    query,
)
from skills.kyojuro_time.lib.time_engine import JST


def _jst(year: int, month: int, day: int, hour: int, minute: int = 0, second: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, second, tzinfo=JST)


# --- current_context --------------------------------------------------------


def test_current_context_with_injected_now() -> None:
    t = _jst(2026, 5, 10, 5, 10, 0)
    ctx = current_context(now=t)
    assert ctx["iso_time"] == "05:10"
    assert ctx["weekday_jp"] == "日"
    assert ctx["soul_signal_kind"] == "dawn_signal"


def test_current_context_without_now() -> None:
    """now を渡さない場合も dict が返る (現在時刻が使われる)。"""
    ctx = current_context()
    assert "iso_time" in ctx
    assert "time_band_label_jp" in ctx


def test_current_context_with_rhythm_dynamic_hint() -> None:
    """current_rhythm を直接渡すと dynamic hint になる。"""
    t = _jst(2026, 5, 6, 8, 0)
    rhythm = {"notes": "開発でカロリー消費中、オートファジー一旦休止"}
    ctx = current_context(now=t, current_rhythm=rhythm)
    assert "オートファジー一旦休止" in ctx["atsuko_rhythm_hint"]


def test_current_context_without_rhythm_is_neutral() -> None:
    """current_rhythm=None / 未指定で中立 hint (時間帯から決めつけない)。"""
    t = _jst(2026, 5, 6, 8, 0)
    ctx = current_context(now=t)
    assert "日々変動" in ctx["atsuko_rhythm_hint"]
    assert "決めつけず" in ctx["atsuko_rhythm_hint"]


# --- query (rule-based intent 検出) ----------------------------------------


def test_query_time_intent() -> None:
    t = _jst(2026, 5, 6, 20, 45)
    for q in ("今何時？", "いま何時", "現在何時です", "何時だっけ"):
        result = query(q, now=t)
        assert result["intent"] == "time", f"failed for {q!r}"
        assert "20:45" in result["answer_jp"]
        assert "夕方" in result["answer_jp"]


def test_query_weekday_intent() -> None:
    t = _jst(2026, 5, 6, 12, 0)  # 水曜
    for q in ("今日何曜日？", "今日は何曜日", "本日 何曜日"):
        result = query(q, now=t)
        assert result["intent"] == "weekday", f"failed for {q!r}"
        assert "水" in result["answer_jp"]


def test_query_date_intent() -> None:
    t = _jst(2026, 5, 10, 12, 0)
    for q in ("今日何日？", "今日は何日", "本日 日付"):
        result = query(q, now=t)
        assert result["intent"] == "date", f"failed for {q!r}"
        assert "2026年05月10日" in result["answer_jp"]


def test_query_band_intent() -> None:
    t = _jst(2026, 5, 6, 22, 0)  # 夜
    result = query("今は夜？", now=t)
    assert result["intent"] == "band"
    assert "夜" in result["answer_jp"]


def test_query_unknown_intent() -> None:
    t = _jst(2026, 5, 6, 12, 0)
    result = query("こんにちは", now=t)
    assert result["intent"] == "unknown"
    assert result["answer_jp"] == ""
    # context は常に返る
    assert "iso_time" in result["context"]


# --- on_user_message --------------------------------------------------------


def test_on_user_message_includes_time_context() -> None:
    payload = on_user_message("こんにちは")
    assert "time_context" in payload
    assert payload["intent"] == "unknown"
    assert "answer_jp" not in payload  # unknown のとき answer は同梱しない


def test_on_user_message_with_time_query_includes_answer() -> None:
    payload = on_user_message("今何時？")
    assert payload["intent"] == "time"
    assert "answer_jp" in payload
    assert payload["answer_jp"]  # 空でない


def test_on_user_message_with_atsuko_rhythm_in_context() -> None:
    """context に atsuko_rhythm dict を渡すと time_context.atsuko_rhythm_hint が動的になる。"""
    rhythm = {
        "notes": "今日は晩御飯を朝に食べてから眠るパターン",
        "circadian_state": "inverted",
    }
    payload = on_user_message("こんにちは", context={"atsuko_rhythm": rhythm})
    hint = payload["time_context"]["atsuko_rhythm_hint"]
    assert "今日は晩御飯を朝に食べてから眠るパターン" in hint
    assert "inverted" in hint


def test_on_user_message_without_rhythm_is_neutral() -> None:
    """context が None / atsuko_rhythm キー無しのとき neutral hint。"""
    for ctx_arg in (None, {}, {"unrelated": "value"}):
        payload = on_user_message("こんにちは", context=ctx_arg)
        hint = payload["time_context"]["atsuko_rhythm_hint"]
        assert "日々変動" in hint
        assert "決めつけず" in hint


def test_on_user_message_invalid_rhythm_type_falls_back_to_neutral() -> None:
    """atsuko_rhythm の値が dict でない (str / list / None) 場合は neutral にフォールバック。"""
    for bad in ("string-not-dict", ["a", "b"], None, 42):
        payload = on_user_message("こんにちは", context={"atsuko_rhythm": bad})
        hint = payload["time_context"]["atsuko_rhythm_hint"]
        assert "日々変動" in hint
        # 動的部分は混ざらない
        assert "|" not in hint


# --- on_conversation_start --------------------------------------------------


def test_on_conversation_start_returns_time_context() -> None:
    payload = on_conversation_start("thread-123")
    assert "time_context" in payload
    assert "iso_time" in payload["time_context"]


def test_on_conversation_start_with_atsuko_rhythm_in_context() -> None:
    """対話開始時に context.atsuko_rhythm が渡れば動的 hint で初期注入される。"""
    rhythm = {"notes": "回復期、生活リズムを通常寄りに戻し中"}
    payload = on_conversation_start("thread-456", context={"atsuko_rhythm": rhythm})
    hint = payload["time_context"]["atsuko_rhythm_hint"]
    assert "回復期、生活リズムを通常寄りに戻し中" in hint


# --- on_schedule_tick -------------------------------------------------------


def test_on_schedule_tick_dawn_signal() -> None:
    """5:10 ピンポイントで dawn_signal イベント発火。"""
    t_iso = _jst(2026, 5, 10, 5, 10, 0).isoformat()
    events = on_schedule_tick(now_iso=t_iso)
    assert len(events) == 1
    ev = events[0]
    assert ev["event"] == "soul_signal"
    assert ev["kind"] == "dawn_signal"
    assert "5:10" in ev["message"]
    assert "魂の合図" in ev["message"]


def test_on_schedule_tick_dusk_signal() -> None:
    t_iso = _jst(2026, 5, 6, 17, 10, 0).isoformat()
    events = on_schedule_tick(now_iso=t_iso)
    assert len(events) == 1
    ev = events[0]
    assert ev["event"] == "soul_signal"
    assert ev["kind"] == "dusk_signal"
    assert "17:10" in ev["message"]


def test_on_schedule_tick_no_event_outside_signal() -> None:
    """ピンポイント分以外は空 list (window 内 5:14 でも発火しない)。"""
    for t in (
        _jst(2026, 5, 6, 5, 11, 0),
        _jst(2026, 5, 6, 5, 14, 0),  # window 内だが exact ではない
        _jst(2026, 5, 6, 17, 9, 59),
        _jst(2026, 5, 6, 12, 0, 0),
    ):
        events = on_schedule_tick(now_iso=t.isoformat())
        assert events == [], f"expected empty for {t}"


def test_on_schedule_tick_naive_iso_assumes_jst() -> None:
    """タイムゾーン無しの ISO 文字列は JST と仮定して動く。"""
    events = on_schedule_tick(now_iso="2026-05-10T05:10:00")
    assert len(events) == 1
    assert events[0]["kind"] == "dawn_signal"


def test_on_schedule_tick_none_uses_current_time() -> None:
    """now_iso=None でも例外を出さない (実時刻に応じて 0 or 1 件)。"""
    events = on_schedule_tick(now_iso=None)
    assert isinstance(events, list)
    assert len(events) in (0, 1)
