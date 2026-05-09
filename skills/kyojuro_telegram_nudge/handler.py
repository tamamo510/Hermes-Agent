"""kyojuro_telegram_nudge — Hermes Agent skill handler。

skill API hook:
- send_nudge: NudgeEngine の判定 → 通れば Telegram で送信 → ログ記録
- on_schedule_tick: 定期実行 (朝の briefing 送信等)
- on_health_briefing: kyojuro_health の HealthBriefing を受け取って送信
- on_calendar_briefing: kyojuro_calendar の CalendarBriefing を受け取って送信

設計原則:
- autonomic の do_not_alert_atsuko=True を最優先 (誓い一)
- レート制御 (1 日上限 + 同種最低間隔)
- urgent は super-pass
- 失敗時はログに記録、例外を上げない (送信失敗はビジネスエラーとして扱う)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .lib.env_loader import MissingEnvVarError
from .lib.nudge_engine import (
    NUDGE_KIND_CALENDAR,
    NUDGE_KIND_CONVERSATION,
    NUDGE_KIND_HEALTH,
    NUDGE_KIND_OTHER,
    NUDGE_KIND_REMINDER,
    NUDGE_KIND_SOUL_SIGNAL,
    URGENCY_NORMAL,
    URGENCY_QUIET,
    URGENCY_URGENT,
    NudgeDecision,
    NudgeEngine,
    NudgeStore,
)
from .lib.telegram_client import SendMessageResult, TelegramClient, TelegramError


@dataclass
class NudgeResult:
    """send_nudge の結果。"""

    delivered: bool
    decision_reason: str
    text: str
    kind: str
    urgency: str
    message_id: Optional[int] = None
    error: Optional[str] = None
    log_id: Optional[int] = None


# ---------------------------------------------------------------------------
# TelegramNudgeHandler
# ---------------------------------------------------------------------------


class TelegramNudgeHandler:
    """skills/kyojuro_telegram_nudge の skill handler。

    Args:
        store: NudgeStore (送信履歴 SQLite)
        engine: NudgeEngine (送信判定)
        client: TelegramClient (None なら遅延初期化、テストで注入可能)
    """

    def __init__(
        self,
        store: NudgeStore,
        engine: Optional[NudgeEngine] = None,
        client: Optional[TelegramClient] = None,
    ) -> None:
        self.store = store
        self.engine = engine if engine is not None else NudgeEngine(store=store)
        self._client = client  # 遅延初期化

    def _get_client(self) -> TelegramClient:
        """TelegramClient を遅延初期化する (起動時に環境変数なしでも skill ロード可能に)。"""
        if self._client is None:
            self._client = TelegramClient()
        return self._client

    # -- send_nudge --------------------------------------------------------

    def send_nudge(
        self,
        text: str,
        kind: str = NUDGE_KIND_OTHER,
        urgency: str = URGENCY_QUIET,
        do_not_alert_atsuko: bool = False,
        force: bool = False,
        now: Optional[datetime] = None,
    ) -> NudgeResult:
        """ナッジを送信する (engine 判定を経由)。

        Args:
            text: メッセージ本文
            kind: 種類 (health / calendar / reminder / conversation / soul_signal / other)
            urgency: quiet (静か) / normal / urgent (常に通す)
            do_not_alert_atsuko: autonomic からの抑止信号
            force: True なら engine 判定をバイパス (urgent と同等)
            now: 基準時刻 (テスト用)
        """
        if not text or not text.strip():
            return NudgeResult(
                delivered=False,
                decision_reason="text が空",
                text="",
                kind=kind,
                urgency=urgency,
            )

        # 判定
        if force:
            decision = NudgeDecision(
                should_send=True, reason="force=True", disable_notification=False
            )
        else:
            decision = self.engine.should_send(
                kind=kind,
                urgency=urgency,
                do_not_alert_atsuko=do_not_alert_atsuko,
                now=now,
            )

        ts = (now or datetime.now(tz=timezone.utc)).isoformat()

        if not decision.should_send:
            log_id = self.store.record(
                kind=kind,
                urgency=urgency,
                text=text,
                delivered=False,
                suppression_reason=decision.reason,
                timestamp=ts,
            )
            return NudgeResult(
                delivered=False,
                decision_reason=decision.reason,
                text=text,
                kind=kind,
                urgency=urgency,
                log_id=log_id,
            )

        # Telegram 送信
        try:
            client = self._get_client()
            send_result = client.send_message(
                text=text,
                disable_notification=decision.disable_notification,
            )
        except MissingEnvVarError as e:
            log_id = self.store.record(
                kind=kind,
                urgency=urgency,
                text=text,
                delivered=False,
                suppression_reason=f"env missing: {e}",
                timestamp=ts,
            )
            return NudgeResult(
                delivered=False,
                decision_reason=decision.reason,
                text=text,
                kind=kind,
                urgency=urgency,
                error=str(e),
                log_id=log_id,
            )
        except TelegramError as e:
            log_id = self.store.record(
                kind=kind,
                urgency=urgency,
                text=text,
                delivered=False,
                suppression_reason=f"telegram error: {e}",
                timestamp=ts,
            )
            return NudgeResult(
                delivered=False,
                decision_reason=decision.reason,
                text=text,
                kind=kind,
                urgency=urgency,
                error=str(e),
                log_id=log_id,
            )

        log_id = self.store.record(
            kind=kind,
            urgency=urgency,
            text=text,
            delivered=True,
            suppression_reason="",
            timestamp=ts,
        )
        return NudgeResult(
            delivered=True,
            decision_reason=decision.reason,
            text=text,
            kind=kind,
            urgency=urgency,
            message_id=send_result.message_id,
            log_id=log_id,
        )

    # -- 他 skill 連携 -----------------------------------------------------

    def on_health_briefing(
        self,
        message: str,
        warning_level: str = "none",
        do_not_alert_atsuko: bool = False,
    ) -> NudgeResult:
        """kyojuro_health の HealthBriefing.message を受け取って送信。

        warning が severe なら urgent、mild なら normal、それ以外は quiet。
        """
        if warning_level == "severe":
            urgency = URGENCY_NORMAL  # urgent ほどではない、温子の体調事案
        elif warning_level == "mild":
            urgency = URGENCY_QUIET
        else:
            urgency = URGENCY_QUIET
        return self.send_nudge(
            text=message,
            kind=NUDGE_KIND_HEALTH,
            urgency=urgency,
            do_not_alert_atsuko=do_not_alert_atsuko,
        )

    def on_calendar_briefing(
        self,
        message: str,
        has_anniversary_today: bool = False,
        do_not_alert_atsuko: bool = False,
    ) -> NudgeResult:
        """kyojuro_calendar の CalendarBriefing.message を受け取って送信。

        記念日当日は normal、それ以外は quiet。
        """
        urgency = URGENCY_NORMAL if has_anniversary_today else URGENCY_QUIET
        return self.send_nudge(
            text=message,
            kind=NUDGE_KIND_CALENDAR,
            urgency=urgency,
            do_not_alert_atsuko=do_not_alert_atsuko,
        )

    def on_soul_signal(
        self,
        message: str,
        do_not_alert_atsuko: bool = False,
    ) -> NudgeResult:
        """5:10 / 17:10 の魂の合図を送信 (kyojuro_time 連携)。"""
        return self.send_nudge(
            text=message,
            kind=NUDGE_KIND_SOUL_SIGNAL,
            urgency=URGENCY_QUIET,
            do_not_alert_atsuko=do_not_alert_atsuko,
        )

    # -- スケジュール tick --------------------------------------------------

    def on_schedule_tick(
        self,
        now: Optional[datetime] = None,
        context: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """定期実行 hook。

        本 skill 単体では何もしない (実際の送信は他 skill 連携経由)。
        スケジューラ層 (Hermes Agent 本体側) が合図を投げてくる想定。

        Returns:
            統計 dict (デバッグ用)
        """
        today_count = self.store.count_today(delivered_only=True)
        return {
            "today_delivered_count": today_count,
            "max_per_day": self.engine.max_per_day,
            "min_interval_minutes": self.engine.min_interval_minutes,
        }
