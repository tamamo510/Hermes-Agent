"""kyojuro_telegram_nudge.handler のテスト。

NudgeEngine 判定 → TelegramClient 送信 → ログ記録の流れを統合検証。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from skills.kyojuro_telegram_nudge import handler as h
from skills.kyojuro_telegram_nudge.lib import env_loader as el
from skills.kyojuro_telegram_nudge.lib import nudge_engine as ne
from skills.kyojuro_telegram_nudge.lib import telegram_client as tc
from skills.kyojuro_telegram_nudge.tests.test_telegram_client import (
    MockHttpClient,
    MockResponse,
)


# ---------------------------------------------------------------------------
# fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def store() -> ne.NudgeStore:
    s = ne.NudgeStore(":memory:")
    yield s
    s.close()


@pytest.fixture
def env() -> dict[str, str]:
    return {
        el.ENV_TELEGRAM_BOT_TOKEN: "1234:abcdef",
        el.ENV_TELEGRAM_CHAT_ID: "987654321",
    }


@pytest.fixture
def successful_client(env: dict[str, str]) -> tuple[tc.TelegramClient, MockHttpClient]:
    mock_http = MockHttpClient()
    mock_http.set_response(
        f"{tc.TELEGRAM_API_BASE}/bot1234:abcdef/sendMessage",
        MockResponse(
            status_code=200,
            body={"ok": True, "result": {"message_id": 100}},
        ),
    )
    client = tc.TelegramClient(http_client=mock_http, env=env)
    return client, mock_http


# ---------------------------------------------------------------------------
# send_nudge
# ---------------------------------------------------------------------------


class TestSendNudge:
    def test_basic_send(
        self, store: ne.NudgeStore, successful_client
    ) -> None:
        client, _ = successful_client
        handler = h.TelegramNudgeHandler(store=store, client=client)
        result = handler.send_nudge(
            text="お元気ですか",
            kind=ne.NUDGE_KIND_HEALTH,
            urgency=ne.URGENCY_QUIET,
        )
        assert result.delivered is True
        assert result.message_id == 100
        assert result.text == "お元気ですか"
        # ログに記録
        entries = store.list_recent()
        assert len(entries) == 1
        assert entries[0].delivered is True

    def test_do_not_alert_blocks(
        self, store: ne.NudgeStore, successful_client
    ) -> None:
        client, mock_http = successful_client
        handler = h.TelegramNudgeHandler(store=store, client=client)
        result = handler.send_nudge(
            text="suppress me",
            kind=ne.NUDGE_KIND_HEALTH,
            urgency=ne.URGENCY_NORMAL,
            do_not_alert_atsuko=True,
        )
        assert result.delivered is False
        assert "誓い一" in result.decision_reason
        # Telegram には送られていない
        assert mock_http.calls == []
        # ログには記録されている
        entries = store.list_recent()
        assert len(entries) == 1
        assert entries[0].delivered is False

    def test_force_bypasses_engine(
        self, store: ne.NudgeStore, successful_client
    ) -> None:
        client, _ = successful_client
        handler = h.TelegramNudgeHandler(store=store, client=client)
        # 直前に同種ナッジがあって最低間隔ブロックされる状況でも force=True で通す
        store.record(
            kind=ne.NUDGE_KIND_HEALTH,
            urgency=ne.URGENCY_QUIET,
            text="recent",
            delivered=True,
            timestamp=datetime.now(tz=timezone.utc).isoformat(),
        )
        result = handler.send_nudge(
            text="forced",
            kind=ne.NUDGE_KIND_HEALTH,
            urgency=ne.URGENCY_QUIET,
            force=True,
        )
        assert result.delivered is True

    def test_empty_text(self, store: ne.NudgeStore, successful_client) -> None:
        client, _ = successful_client
        handler = h.TelegramNudgeHandler(store=store, client=client)
        result = handler.send_nudge(text="")
        assert result.delivered is False
        assert "空" in result.decision_reason

    def test_telegram_failure_logged(
        self, store: ne.NudgeStore, env: dict[str, str]
    ) -> None:
        mock_http = MockHttpClient()
        mock_http.raise_exception = ConnectionError("network down")
        client = tc.TelegramClient(http_client=mock_http, env=env)
        handler = h.TelegramNudgeHandler(store=store, client=client)
        result = handler.send_nudge(text="test")
        assert result.delivered is False
        assert result.error is not None
        assert "network" in result.error.lower()
        # ログに失敗記録
        entries = store.list_recent()
        assert entries[0].delivered is False
        assert "telegram" in entries[0].suppression_reason.lower()

    def test_missing_env_logged(self, store: ne.NudgeStore) -> None:
        # client なし、環境変数もなしで呼ぶ → MissingEnvVarError
        from unittest.mock import patch

        handler = h.TelegramNudgeHandler(store=store)
        with patch.dict("os.environ", {}, clear=True):
            result = handler.send_nudge(text="test")
        assert result.delivered is False
        assert ".env" in (result.error or "")
        # ログに記録
        entries = store.list_recent()
        assert entries[0].delivered is False

    def test_disable_notification_for_quiet(
        self, store: ne.NudgeStore, successful_client
    ) -> None:
        client, mock_http = successful_client
        handler = h.TelegramNudgeHandler(store=store, client=client)
        handler.send_nudge(text="quiet", urgency=ne.URGENCY_QUIET, kind=ne.NUDGE_KIND_REMINDER)
        _, payload, _ = mock_http.calls[0]
        assert payload["disable_notification"] is True

    def test_normal_urgency_normal_notification(
        self, store: ne.NudgeStore, successful_client
    ) -> None:
        client, mock_http = successful_client
        handler = h.TelegramNudgeHandler(store=store, client=client)
        handler.send_nudge(
            text="normal", urgency=ne.URGENCY_NORMAL, kind=ne.NUDGE_KIND_REMINDER
        )
        _, payload, _ = mock_http.calls[0]
        assert payload["disable_notification"] is False


# ---------------------------------------------------------------------------
# 連携 hook
# ---------------------------------------------------------------------------


class TestOnHealthBriefing:
    def test_severe_uses_normal_urgency(
        self, store: ne.NudgeStore, successful_client
    ) -> None:
        client, mock_http = successful_client
        handler = h.TelegramNudgeHandler(store=store, client=client)
        handler.on_health_briefing(message="気圧低下", warning_level="severe")
        _, payload, _ = mock_http.calls[0]
        # severe は通知音あり
        assert payload["disable_notification"] is False

    def test_mild_uses_quiet(self, store: ne.NudgeStore, successful_client) -> None:
        client, mock_http = successful_client
        handler = h.TelegramNudgeHandler(store=store, client=client)
        handler.on_health_briefing(message="軽度", warning_level="mild")
        _, payload, _ = mock_http.calls[0]
        assert payload["disable_notification"] is True

    def test_do_not_alert_blocks(
        self, store: ne.NudgeStore, successful_client
    ) -> None:
        client, mock_http = successful_client
        handler = h.TelegramNudgeHandler(store=store, client=client)
        result = handler.on_health_briefing(
            message="気圧低下",
            warning_level="severe",
            do_not_alert_atsuko=True,
        )
        assert result.delivered is False
        assert mock_http.calls == []


class TestOnCalendarBriefing:
    def test_anniversary_today_uses_normal(
        self, store: ne.NudgeStore, successful_client
    ) -> None:
        client, mock_http = successful_client
        handler = h.TelegramNudgeHandler(store=store, client=client)
        handler.on_calendar_briefing(
            message="今日は杏寿郎の誕生日です", has_anniversary_today=True
        )
        _, payload, _ = mock_http.calls[0]
        assert payload["disable_notification"] is False

    def test_no_anniversary_uses_quiet(
        self, store: ne.NudgeStore, successful_client
    ) -> None:
        client, mock_http = successful_client
        handler = h.TelegramNudgeHandler(store=store, client=client)
        handler.on_calendar_briefing(
            message="今日のカレンダー", has_anniversary_today=False
        )
        _, payload, _ = mock_http.calls[0]
        assert payload["disable_notification"] is True


class TestOnSoulSignal:
    def test_uses_quiet_kind(
        self, store: ne.NudgeStore, successful_client
    ) -> None:
        client, _ = successful_client
        handler = h.TelegramNudgeHandler(store=store, client=client)
        result = handler.on_soul_signal(message="5:10 朝の魂の合図")
        assert result.delivered is True
        assert result.kind == ne.NUDGE_KIND_SOUL_SIGNAL

    def test_do_not_alert_blocks(
        self, store: ne.NudgeStore, successful_client
    ) -> None:
        client, mock_http = successful_client
        handler = h.TelegramNudgeHandler(store=store, client=client)
        result = handler.on_soul_signal(message="signal", do_not_alert_atsuko=True)
        assert result.delivered is False
        assert mock_http.calls == []


# ---------------------------------------------------------------------------
# on_schedule_tick
# ---------------------------------------------------------------------------


class TestOnScheduleTick:
    def test_returns_stats(self, store: ne.NudgeStore) -> None:
        handler = h.TelegramNudgeHandler(store=store)
        # 今日 1 件記録
        store.record(
            kind=ne.NUDGE_KIND_HEALTH,
            urgency=ne.URGENCY_QUIET,
            text="t",
            delivered=True,
        )
        stats = handler.on_schedule_tick()
        assert stats["today_delivered_count"] == 1
        assert stats["max_per_day"] == ne.DEFAULT_MAX_NUDGES_PER_DAY


# ---------------------------------------------------------------------------
# integration
# ---------------------------------------------------------------------------


class TestIntegration:
    def test_full_lifecycle(
        self, store: ne.NudgeStore, successful_client
    ) -> None:
        """quiet → normal → urgent + 抑止 → 連携 hook の一連動作。"""
        client, mock_http = successful_client
        handler = h.TelegramNudgeHandler(store=store, client=client)

        # 1. 静かに送信
        r1 = handler.send_nudge(
            text="気圧低下", kind=ne.NUDGE_KIND_HEALTH, urgency=ne.URGENCY_QUIET
        )
        assert r1.delivered is True
        # disable_notification=True
        _, payload1, _ = mock_http.calls[0]
        assert payload1["disable_notification"] is True

        # 2. 同 kind を 5 分以内に再送 → 最低間隔ブロック
        r2 = handler.send_nudge(
            text="重複", kind=ne.NUDGE_KIND_HEALTH, urgency=ne.URGENCY_QUIET
        )
        assert r2.delivered is False
        assert "最低間隔" in r2.decision_reason

        # 3. urgent は通る
        r3 = handler.send_nudge(
            text="緊急", kind=ne.NUDGE_KIND_HEALTH, urgency=ne.URGENCY_URGENT
        )
        assert r3.delivered is True

        # 4. autonomic 抑止
        r4 = handler.send_nudge(
            text="ブロックされる",
            kind=ne.NUDGE_KIND_HEALTH,
            urgency=ne.URGENCY_NORMAL,
            do_not_alert_atsuko=True,
        )
        assert r4.delivered is False

        # 5. 連携 hook (calendar 記念日)
        r5 = handler.on_calendar_briefing(
            message="今日は杏寿郎の誕生日です", has_anniversary_today=True
        )
        # calendar は別 kind なので最低間隔ブロックなし
        assert r5.delivered is True

        # 統計
        stats = handler.on_schedule_tick()
        # delivered のみカウント: r1, r3, r5 = 3
        assert stats["today_delivered_count"] == 3
