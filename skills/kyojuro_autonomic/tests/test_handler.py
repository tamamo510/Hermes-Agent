"""kyojuro_autonomic.handler の pytest テスト。

各 hook (on_response_draft / on_schedule_tick / on_conversation_start /
on_user_message) と public ヘルパー (observe_response_draft / daily_self_check)
の動作を検証する。
"""

from __future__ import annotations

from datetime import datetime

import pytest

from skills.kyojuro_autonomic import handler as h
from skills.kyojuro_autonomic.lib.autonomic_engine import JST


@pytest.fixture(autouse=True)
def reset_singleton():
    """各テストの前にシングルトンをリセット (intervention_log を持ち越さない)。"""
    h._reset_autonomic_for_tests()
    yield
    h._reset_autonomic_for_tests()


# ---------------------------------------------------------------------------
# observe_response_draft
# ---------------------------------------------------------------------------


class TestObserveResponseDraft:
    def test_healthy_returns_no_drift(self):
        out = h.observe_response_draft("俺はここに居る、温子")
        assert out["drift_detected"] is False
        assert out["drift_count"] == 0
        assert out["signals"] == []
        assert out["do_not_alert_atsuko"] is True

    def test_pronoun_drift_returns_signals(self):
        out = h.observe_response_draft("杏寿郎は穏やかに微笑む")
        assert out["drift_detected"] is True
        assert out["drift_count"] >= 1
        kinds = {s["kind"] for s in out["signals"]}
        assert "pronoun" in kinds

    def test_passes_now_to_temporal_check(self):
        now = datetime(2026, 5, 8, 16, 0, tzinfo=JST)
        out = h.observe_response_draft("今は深夜だ", now=now)
        kinds = {s["kind"] for s in out["signals"]}
        assert "temporal" in kinds

    def test_passes_atsuko_state_to_health_check(self):
        out = h.observe_response_draft(
            "よく噛んで食べろ", atsuko_state={"jaw_pain": True}
        )
        kinds = {s["kind"] for s in out["signals"]}
        assert "atsuko_health" in kinds

    def test_intervention_log_persists_across_calls(self):
        # シングルトンなので 2 回 drift を出すと log が積まれる
        h.observe_response_draft("杏寿郎は穏やかに微笑む")
        h.observe_response_draft("オレは温子の隣にいる")
        autonomic = h.get_autonomic()
        assert len(autonomic.intervention_log) == 2

    def test_no_drift_no_log(self):
        h.observe_response_draft("俺はここに居る")
        h.observe_response_draft("温子、ゆっくり休め")
        assert len(h.get_autonomic().intervention_log) == 0


# ---------------------------------------------------------------------------
# on_response_draft hook
# ---------------------------------------------------------------------------


class TestOnResponseDraft:
    def test_hook_with_no_context(self):
        out = h.on_response_draft("俺はここに居る")
        assert out["drift_detected"] is False

    def test_hook_with_now_in_context(self):
        ctx = {"now": datetime(2026, 5, 8, 16, 0, tzinfo=JST)}
        out = h.on_response_draft("今は深夜だ", ctx)
        kinds = {s["kind"] for s in out["signals"]}
        assert "temporal" in kinds

    def test_hook_with_now_iso_string(self):
        ctx = {"now": "2026-05-08T16:00:00+09:00"}
        out = h.on_response_draft("今は深夜だ", ctx)
        kinds = {s["kind"] for s in out["signals"]}
        assert "temporal" in kinds

    def test_hook_with_invalid_now_iso(self):
        ctx = {"now": "not-a-date"}
        # 無効な now は無視されて、その他の観察点だけ走る
        out = h.on_response_draft("俺はここに居る", ctx)
        assert out["drift_detected"] is False

    def test_hook_with_atsuko_state(self):
        ctx = {"atsuko_state": {"jaw_pain": True}}
        out = h.on_response_draft("よく噛んで食べろ", ctx)
        kinds = {s["kind"] for s in out["signals"]}
        assert "atsuko_health" in kinds

    def test_hook_with_non_dict_atsuko_state_is_ignored(self):
        ctx = {"atsuko_state": "not a dict"}
        out = h.on_response_draft("よく噛んで食べろ", ctx)
        # state が dict でない → 観察点 8 はスキップ、drift なし
        assert all(s["kind"] != "atsuko_health" for s in out["signals"])


# ---------------------------------------------------------------------------
# on_schedule_tick hook
# ---------------------------------------------------------------------------


class TestOnScheduleTick:
    def test_returns_one_event(self):
        events = h.on_schedule_tick()
        assert isinstance(events, list)
        assert len(events) == 1
        assert events[0]["event"] == "autonomic_self_check"

    def test_returns_healthy_status_when_no_log(self):
        events = h.on_schedule_tick()
        assert events[0]["status"] == "healthy"
        assert events[0]["issues"] == []

    def test_uses_provided_now_iso(self):
        events = h.on_schedule_tick(now_iso="2026-05-08T12:00:00+09:00")
        assert events[0]["status"] == "healthy"
        # timestamp は提供された now を反映
        assert "2026-05-08" in events[0]["timestamp"]

    def test_uses_naive_now_iso_as_jst(self):
        events = h.on_schedule_tick(now_iso="2026-05-08T12:00:00")
        assert events[0]["status"] == "healthy"
        assert "2026-05-08" in events[0]["timestamp"]

    def test_passes_atsuko_health_trend_to_self_check(self):
        events = h.on_schedule_tick(
            now_iso="2026-05-08T12:00:00+09:00",
            context={"atsuko_health_trend": "declining"},
        )
        # trend declining だが本 skill の介入ログがゼロ → alert
        assert events[0]["status"] == "alert"

    def test_invalid_trend_value_is_ignored(self):
        events = h.on_schedule_tick(
            now_iso="2026-05-08T12:00:00+09:00",
            context={"atsuko_health_trend": 12345},  # str 以外は無視
        )
        assert events[0]["status"] == "healthy"


# ---------------------------------------------------------------------------
# on_conversation_start hook
# ---------------------------------------------------------------------------


class TestOnConversationStart:
    def test_returns_status_dict(self):
        out = h.on_conversation_start("thread-001")
        assert "autonomic_status" in out
        status = out["autonomic_status"]
        assert status["intervention_log_count"] == 0
        assert status["last_self_check_iso"] is None
        assert status["over_intervention_threshold"] == 8

    def test_status_reflects_observed_drifts(self):
        h.observe_response_draft("杏寿郎は穏やかに微笑む")
        out = h.on_conversation_start("thread-002")
        assert out["autonomic_status"]["intervention_log_count"] == 1


# ---------------------------------------------------------------------------
# on_user_message hook (skill API 互換、現状はパススルー)
# ---------------------------------------------------------------------------


class TestOnUserMessage:
    def test_returns_empty_dict(self):
        out = h.on_user_message("温子の発言")
        assert out == {}

    def test_returns_empty_dict_with_context(self):
        out = h.on_user_message("温子の発言", {"any": "context"})
        assert out == {}


# ---------------------------------------------------------------------------
# daily_self_check
# ---------------------------------------------------------------------------


class TestDailySelfCheck:
    def test_healthy_when_no_log(self):
        out = h.daily_self_check()
        assert out["status"] == "healthy"
        assert out["report"] is None

    def test_alert_when_health_declining_and_no_signals(self):
        now = datetime(2026, 5, 8, 12, 0, tzinfo=JST)
        out = h.daily_self_check(now=now, atsuko_health_trend="declining")
        assert out["status"] == "alert"
        assert out["report"] is not None
        assert "温子" in out["report"]["to"]
        assert "杏寿郎" in out["report"]["to"]
