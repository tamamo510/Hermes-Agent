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


# --- on_conversation_start --------------------------------------------------


def test_on_conversation_start_returns_time_context() -> None:
    payload = on_conversation_start("thread-123")
    assert "time_context" in payload
    assert "iso_time" in payload["time_context"]


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
