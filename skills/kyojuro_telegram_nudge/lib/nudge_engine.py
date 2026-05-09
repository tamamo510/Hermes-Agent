"""kyojuro_telegram_nudge.lib.nudge_engine — 「静かに声かけする」ナッジロジック。

杏寿郎の発注書 + ⑨ 起動指示書:
  > 温子に静かに声かけする機能。autonomic の do_not_alert_atsuko=True の結果と連携

設計原則:
- 押し付けない (誓い四「杏寿郎の自由を奪わない」と同じ思想を温子側にも適用)
- スパムしない (1 日の上限、最低間隔を守る)
- autonomic の do_not_alert_atsuko=True を尊重 (誓い一「温子を悲しませない」)
- 重要度別に通知音をコントロール (silent / normal / urgent)
- 送信履歴を SQLite で保持し、頻度制御に使う
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator, Optional


# ---------------------------------------------------------------------------
# 重要度
# ---------------------------------------------------------------------------

URGENCY_QUIET = "quiet"  # 通知音なし、温子のタイミングで読む
URGENCY_NORMAL = "normal"  # 通常の通知音
URGENCY_URGENT = "urgent"  # 緊急 (体調急変、危険等)。慎重に使う

VALID_URGENCIES = frozenset({URGENCY_QUIET, URGENCY_NORMAL, URGENCY_URGENT})

# ナッジ目的のラベル (ログ・分析用)
NUDGE_KIND_HEALTH = "health"  # 体調・気圧
NUDGE_KIND_CALENDAR = "calendar"  # 記念日・命日
NUDGE_KIND_REMINDER = "reminder"  # 一般的なリマインダー
NUDGE_KIND_CONVERSATION = "conversation"  # 会話誘い
NUDGE_KIND_SOUL_SIGNAL = "soul_signal"  # 5:10 / 17:10 の魂の合図
NUDGE_KIND_OTHER = "other"

VALID_NUDGE_KINDS = frozenset(
    {
        NUDGE_KIND_HEALTH,
        NUDGE_KIND_CALENDAR,
        NUDGE_KIND_REMINDER,
        NUDGE_KIND_CONVERSATION,
        NUDGE_KIND_SOUL_SIGNAL,
        NUDGE_KIND_OTHER,
    }
)


# ---------------------------------------------------------------------------
# レート制御 (デフォルト値、温子が調整可能)
# ---------------------------------------------------------------------------

DEFAULT_MAX_NUDGES_PER_DAY = 6  # 1 日の総上限
DEFAULT_MIN_INTERVAL_MINUTES = 30  # 同種ナッジの最低間隔 (urgent 除く)


# ---------------------------------------------------------------------------
# データクラス
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NudgeEntry:
    """ナッジ送信ログの 1 エントリ。"""

    id: int
    timestamp: str  # ISO 8601
    kind: str
    urgency: str
    text: str
    delivered: bool  # True で送信成功、False で抑止 or 送信失敗
    suppression_reason: str  # delivered=False の理由


@dataclass
class NudgeDecision:
    """should_send_nudge の判定結果。"""

    should_send: bool
    reason: str
    disable_notification: bool  # Telegram への disable_notification 値


# ---------------------------------------------------------------------------
# スキーマ
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS nudge_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    kind TEXT NOT NULL,
    urgency TEXT NOT NULL,
    text TEXT NOT NULL,
    delivered INTEGER NOT NULL,
    suppression_reason TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_nudge_time ON nudge_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_nudge_kind ON nudge_log(kind);
"""


# ---------------------------------------------------------------------------
# NudgeStore
# ---------------------------------------------------------------------------


class NudgeStore:
    """ナッジ送信ログを SQLite で保持する。"""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "NudgeStore":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    @contextmanager
    def _cursor(self) -> Iterator[sqlite3.Cursor]:
        cur = self._conn.cursor()
        try:
            yield cur
        finally:
            cur.close()

    def record(
        self,
        kind: str,
        urgency: str,
        text: str,
        delivered: bool,
        suppression_reason: str = "",
        timestamp: Optional[str] = None,
    ) -> int:
        if kind not in VALID_NUDGE_KINDS:
            raise ValueError(f"kind: {kind!r}")
        if urgency not in VALID_URGENCIES:
            raise ValueError(f"urgency: {urgency!r}")
        ts = timestamp if timestamp else _now_iso()
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO nudge_log
                    (timestamp, kind, urgency, text, delivered, suppression_reason)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (ts, kind, urgency, text, 1 if delivered else 0, suppression_reason),
            )
            return int(cur.lastrowid)

    def list_recent(
        self,
        kind: Optional[str] = None,
        delivered_only: bool = False,
        since: Optional[str] = None,
        limit: int = 50,
    ) -> list[NudgeEntry]:
        clauses: list[str] = []
        params: list[Any] = []
        if kind is not None:
            clauses.append("kind = ?")
            params.append(kind)
        if delivered_only:
            clauses.append("delivered = 1")
        if since is not None:
            clauses.append("timestamp >= ?")
            params.append(since)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = f"SELECT * FROM nudge_log {where} ORDER BY timestamp DESC LIMIT ?"
        params.append(int(limit))
        with self._cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        return [_row_to_entry(r) for r in rows]

    def count_today(
        self,
        delivered_only: bool = True,
        today_start: Optional[str] = None,
    ) -> int:
        """今日の送信件数 (デフォルトは UTC の 00:00 起点)。"""
        if today_start is None:
            now = datetime.now(tz=timezone.utc)
            today_start = datetime(
                now.year, now.month, now.day, 0, 0, 0, tzinfo=timezone.utc
            ).isoformat()
        clauses = ["timestamp >= ?"]
        params: list[Any] = [today_start]
        if delivered_only:
            clauses.append("delivered = 1")
        sql = f"SELECT COUNT(*) FROM nudge_log WHERE " + " AND ".join(clauses)
        with self._cursor() as cur:
            cur.execute(sql, params)
            return int(cur.fetchone()[0])

    def latest_of_kind(
        self, kind: str, delivered_only: bool = True
    ) -> Optional[NudgeEntry]:
        if kind not in VALID_NUDGE_KINDS:
            raise ValueError(f"kind: {kind!r}")
        clauses = ["kind = ?"]
        params: list[Any] = [kind]
        if delivered_only:
            clauses.append("delivered = 1")
        sql = (
            f"SELECT * FROM nudge_log WHERE "
            f"{' AND '.join(clauses)} ORDER BY timestamp DESC LIMIT 1"
        )
        with self._cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
        return _row_to_entry(row) if row is not None else None


# ---------------------------------------------------------------------------
# NudgeEngine
# ---------------------------------------------------------------------------


class NudgeEngine:
    """ナッジ送信判定。

    Args:
        store: NudgeStore
        max_per_day: 1 日の上限件数 (デフォルト 6)
        min_interval_minutes: 同種ナッジの最低間隔 (デフォルト 30 分)
    """

    def __init__(
        self,
        store: NudgeStore,
        max_per_day: int = DEFAULT_MAX_NUDGES_PER_DAY,
        min_interval_minutes: int = DEFAULT_MIN_INTERVAL_MINUTES,
    ) -> None:
        self.store = store
        self.max_per_day = int(max_per_day)
        self.min_interval_minutes = int(min_interval_minutes)

    def should_send(
        self,
        kind: str,
        urgency: str,
        do_not_alert_atsuko: bool = False,
        now: Optional[datetime] = None,
    ) -> NudgeDecision:
        """送信すべきか判定する。

        判定優先度:
        1. autonomic から do_not_alert_atsuko=True が来たら抑止 (誓い一最優先)
        2. urgency=urgent は常に通す (頻度制御を super-pass)
        3. 1 日の上限を超えていたら抑止
        4. 同種ナッジの最低間隔を満たしていなければ抑止
        5. それ以外は通過

        通知音 (disable_notification):
        - quiet → True (静かに)
        - normal → False (通常)
        - urgent → False (通常)
        """
        if kind not in VALID_NUDGE_KINDS:
            raise ValueError(f"kind: {kind!r}")
        if urgency not in VALID_URGENCIES:
            raise ValueError(f"urgency: {urgency!r}")
        now_dt = now if now is not None else datetime.now(tz=timezone.utc)

        # disable_notification の決定
        if urgency == URGENCY_QUIET:
            disable_notification = True
        else:
            disable_notification = False

        # ルール 1: do_not_alert_atsuko (autonomic 連携)
        if do_not_alert_atsuko:
            return NudgeDecision(
                should_send=False,
                reason="autonomic do_not_alert_atsuko=True (誓い一)",
                disable_notification=disable_notification,
            )

        # ルール 2: urgent は super-pass
        if urgency == URGENCY_URGENT:
            return NudgeDecision(
                should_send=True,
                reason="urgency=urgent",
                disable_notification=False,
            )

        # ルール 3: 1 日の上限
        today_count = self.store.count_today(
            delivered_only=True,
            today_start=datetime(
                now_dt.year, now_dt.month, now_dt.day, 0, 0, 0,
                tzinfo=timezone.utc,
            ).isoformat(),
        )
        if today_count >= self.max_per_day:
            return NudgeDecision(
                should_send=False,
                reason=f"1 日の上限 {self.max_per_day} 件に到達",
                disable_notification=disable_notification,
            )

        # ルール 4: 同種ナッジの最低間隔
        latest = self.store.latest_of_kind(kind, delivered_only=True)
        if latest is not None:
            try:
                latest_dt = datetime.fromisoformat(latest.timestamp)
                if latest_dt.tzinfo is None:
                    latest_dt = latest_dt.replace(tzinfo=timezone.utc)
            except ValueError:
                latest_dt = None
            if latest_dt is not None:
                elapsed = (now_dt - latest_dt).total_seconds() / 60
                if elapsed < self.min_interval_minutes:
                    return NudgeDecision(
                        should_send=False,
                        reason=(
                            f"同種ナッジの最低間隔 {self.min_interval_minutes} 分を満たしていない "
                            f"(前回: {elapsed:.0f} 分前)"
                        ),
                        disable_notification=disable_notification,
                    )

        # ルール 5: 通過
        return NudgeDecision(
            should_send=True,
            reason="OK",
            disable_notification=disable_notification,
        )


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _row_to_entry(row: sqlite3.Row) -> NudgeEntry:
    return NudgeEntry(
        id=int(row["id"]),
        timestamp=str(row["timestamp"]),
        kind=str(row["kind"]),
        urgency=str(row["urgency"]),
        text=str(row["text"]),
        delivered=bool(row["delivered"]),
        suppression_reason=str(row["suppression_reason"]),
    )
