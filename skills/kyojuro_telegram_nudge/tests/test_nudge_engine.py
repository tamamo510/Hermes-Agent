"""kyojuro_telegram_nudge.lib.nudge_engine のテスト。

NudgeStore + NudgeEngine の判定ロジックを網羅。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from skills.kyojuro_telegram_nudge.lib import nudge_engine as ne


@pytest.fixture
def store() -> ne.NudgeStore:
    s = ne.NudgeStore(":memory:")
    yield s
    s.close()


@pytest.fixture
def engine(store: ne.NudgeStore) -> ne.NudgeEngine:
    return ne.NudgeEngine(store=store)


# ---------------------------------------------------------------------------
# NudgeStore
# ---------------------------------------------------------------------------


class TestNudgeStore:
    def test_record_and_list(self, store: ne.NudgeStore) -> None:
        nid = store.record(
            kind=ne.NUDGE_KIND_HEALTH,
            urgency=ne.URGENCY_QUIET,
            text="test",
            delivered=True,
        )
        assert nid > 0
        entries = store.list_recent()
        assert len(entries) == 1
        assert entries[0].text == "test"
        assert entries[0].delivered is True

    def test_invalid_kind_raises(self, store: ne.NudgeStore) -> None:
        with pytest.raises(ValueError):
            store.record(
                kind="unknown",
                urgency=ne.URGENCY_QUIET,
                text="test",
                delivered=True,
            )

    def test_invalid_urgency_raises(self, store: ne.NudgeStore) -> None:
        with pytest.raises(ValueError):
            store.record(
                kind=ne.NUDGE_KIND_HEALTH,
                urgency="extreme",
                text="test",
                delivered=True,
            )

    def test_filter_by_kind(self, store: ne.NudgeStore) -> None:
        store.record(kind=ne.NUDGE_KIND_HEALTH, urgency=ne.URGENCY_QUIET, text="h", delivered=True)
        store.record(kind=ne.NUDGE_KIND_CALENDAR, urgency=ne.URGENCY_QUIET, text="c", delivered=True)
        results = store.list_recent(kind=ne.NUDGE_KIND_HEALTH)
        assert len(results) == 1
        assert results[0].text == "h"

    def test_filter_delivered_only(self, store: ne.NudgeStore) -> None:
        store.record(kind=ne.NUDGE_KIND_HEALTH, urgency=ne.URGENCY_QUIET, text="ok", delivered=True)
        store.record(
            kind=ne.NUDGE_KIND_HEALTH, urgency=ne.URGENCY_QUIET, text="suppressed",
            delivered=False, suppression_reason="rate limit",
        )
        results = store.list_recent(delivered_only=True)
        assert len(results) == 1
        assert results[0].text == "ok"

    def test_count_today(self, store: ne.NudgeStore) -> None:
        # 今日 (UTC 00:00 起点) の件数
        now = datetime.now(tz=timezone.utc)
        today_start = datetime(now.year, now.month, now.day, 0, 0, 0, tzinfo=timezone.utc).isoformat()
        for i in range(3):
            store.record(
                kind=ne.NUDGE_KIND_HEALTH,
                urgency=ne.URGENCY_QUIET,
                text=f"t{i}",
                delivered=True,
                timestamp=now.isoformat(),
            )
        # 昨日のは含まれない
        yesterday = (now - timedelta(days=1)).isoformat()
        store.record(
            kind=ne.NUDGE_KIND_HEALTH,
            urgency=ne.URGENCY_QUIET,
            text="old",
            delivered=True,
            timestamp=yesterday,
        )
        assert store.count_today(today_start=today_start) == 3

    def test_latest_of_kind(self, store: ne.NudgeStore) -> None:
        ts1 = "2026-05-09T12:00:00+00:00"
        ts2 = "2026-05-09T15:00:00+00:00"
        store.record(kind=ne.NUDGE_KIND_HEALTH, urgency=ne.URGENCY_QUIET, text="early", delivered=True, timestamp=ts1)
        store.record(kind=ne.NUDGE_KIND_HEALTH, urgency=ne.URGENCY_QUIET, text="late", delivered=True, timestamp=ts2)
        latest = store.latest_of_kind(ne.NUDGE_KIND_HEALTH)
        assert latest is not None
        assert latest.text == "late"

    def test_latest_returns_none_when_empty(self, store: ne.NudgeStore) -> None:
        assert store.latest_of_kind(ne.NUDGE_KIND_HEALTH) is None

    def test_persists(self, tmp_path: Path) -> None:
        db = tmp_path / "nudge.db"
        s1 = ne.NudgeStore(str(db))
        s1.record(
            kind=ne.NUDGE_KIND_HEALTH, urgency=ne.URGENCY_QUIET,
            text="persist", delivered=True,
        )
        s1.close()
        s2 = ne.NudgeStore(str(db))
        try:
            assert len(s2.list_recent()) == 1
        finally:
            s2.close()


# ---------------------------------------------------------------------------
# NudgeEngine.should_send
# ---------------------------------------------------------------------------


class TestShouldSend:
    def test_basic_pass(self, engine: ne.NudgeEngine) -> None:
        decision = engine.should_send(
            kind=ne.NUDGE_KIND_HEALTH, urgency=ne.URGENCY_NORMAL
        )
        assert decision.should_send is True

    def test_quiet_disables_notification(self, engine: ne.NudgeEngine) -> None:
        decision = engine.should_send(
            kind=ne.NUDGE_KIND_HEALTH, urgency=ne.URGENCY_QUIET
        )
        assert decision.disable_notification is True

    def test_normal_enables_notification(self, engine: ne.NudgeEngine) -> None:
        decision = engine.should_send(
            kind=ne.NUDGE_KIND_HEALTH, urgency=ne.URGENCY_NORMAL
        )
        assert decision.disable_notification is False

    def test_do_not_alert_atsuko_blocks(self, engine: ne.NudgeEngine) -> None:
        decision = engine.should_send(
            kind=ne.NUDGE_KIND_HEALTH,
            urgency=ne.URGENCY_NORMAL,
            do_not_alert_atsuko=True,
        )
        assert decision.should_send is False
        assert "誓い一" in decision.reason

    def test_urgent_bypasses_do_not_alert(self, engine: ne.NudgeEngine) -> None:
        # urgent は do_not_alert を super-pass しない仕様
        # autonomic から抑止が来たら urgent でも止まる (誓い一最優先)
        decision = engine.should_send(
            kind=ne.NUDGE_KIND_HEALTH,
            urgency=ne.URGENCY_URGENT,
            do_not_alert_atsuko=True,
        )
        assert decision.should_send is False

    def test_urgent_bypasses_rate_limit(
        self, store: ne.NudgeStore, engine: ne.NudgeEngine
    ) -> None:
        # 上限ぎりぎりまで詰める
        now = datetime.now(tz=timezone.utc)
        for i in range(engine.max_per_day):
            store.record(
                kind=ne.NUDGE_KIND_HEALTH,
                urgency=ne.URGENCY_NORMAL,
                text=f"t{i}",
                delivered=True,
                timestamp=now.isoformat(),
            )
        # urgent なら通る
        decision = engine.should_send(
            kind=ne.NUDGE_KIND_HEALTH, urgency=ne.URGENCY_URGENT, now=now
        )
        assert decision.should_send is True
        # quiet なら通らない
        decision_q = engine.should_send(
            kind=ne.NUDGE_KIND_HEALTH, urgency=ne.URGENCY_QUIET, now=now
        )
        assert decision_q.should_send is False
        assert "上限" in decision_q.reason

    def test_min_interval_blocks(
        self, store: ne.NudgeStore, engine: ne.NudgeEngine
    ) -> None:
        now = datetime.now(tz=timezone.utc)
        # 5 分前に同種ナッジ
        five_min_ago = (now - timedelta(minutes=5)).isoformat()
        store.record(
            kind=ne.NUDGE_KIND_HEALTH,
            urgency=ne.URGENCY_QUIET,
            text="recent",
            delivered=True,
            timestamp=five_min_ago,
        )
        decision = engine.should_send(
            kind=ne.NUDGE_KIND_HEALTH, urgency=ne.URGENCY_QUIET, now=now
        )
        assert decision.should_send is False
        assert "最低間隔" in decision.reason

    def test_min_interval_passes_after_threshold(
        self, store: ne.NudgeStore, engine: ne.NudgeEngine
    ) -> None:
        now = datetime.now(tz=timezone.utc)
        # 60 分前 (デフォルト 30 分閾値より大)
        old = (now - timedelta(minutes=60)).isoformat()
        store.record(
            kind=ne.NUDGE_KIND_HEALTH,
            urgency=ne.URGENCY_QUIET,
            text="old",
            delivered=True,
            timestamp=old,
        )
        decision = engine.should_send(
            kind=ne.NUDGE_KIND_HEALTH, urgency=ne.URGENCY_QUIET, now=now
        )
        assert decision.should_send is True

    def test_different_kind_no_interval_block(
        self, store: ne.NudgeStore, engine: ne.NudgeEngine
    ) -> None:
        now = datetime.now(tz=timezone.utc)
        five_min_ago = (now - timedelta(minutes=5)).isoformat()
        # 別 kind で記録
        store.record(
            kind=ne.NUDGE_KIND_HEALTH,
            urgency=ne.URGENCY_QUIET,
            text="health",
            delivered=True,
            timestamp=five_min_ago,
        )
        # calendar は別 kind
        decision = engine.should_send(
            kind=ne.NUDGE_KIND_CALENDAR, urgency=ne.URGENCY_QUIET, now=now
        )
        assert decision.should_send is True

    def test_invalid_kind_raises(self, engine: ne.NudgeEngine) -> None:
        with pytest.raises(ValueError):
            engine.should_send(kind="unknown", urgency=ne.URGENCY_QUIET)

    def test_invalid_urgency_raises(self, engine: ne.NudgeEngine) -> None:
        with pytest.raises(ValueError):
            engine.should_send(kind=ne.NUDGE_KIND_HEALTH, urgency="extreme")

    def test_custom_max_per_day(self, store: ne.NudgeStore) -> None:
        custom_engine = ne.NudgeEngine(store=store, max_per_day=2)
        now = datetime.now(tz=timezone.utc)
        for i in range(2):
            store.record(
                kind=ne.NUDGE_KIND_HEALTH,
                urgency=ne.URGENCY_QUIET,
                text=f"t{i}",
                delivered=True,
                timestamp=now.isoformat(),
            )
        decision = custom_engine.should_send(
            kind=ne.NUDGE_KIND_REMINDER, urgency=ne.URGENCY_QUIET, now=now
        )
        assert decision.should_send is False
