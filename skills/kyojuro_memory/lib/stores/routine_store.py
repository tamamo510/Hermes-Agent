"""kyojuro_memory.lib.stores.routine_store — F-3 lifestyle pattern events.

DESIGN.md §2-2 の routines.db スキーマに準拠した SQLite ストア。
プライバシー絶対、全データローカル（DESIGN.md §1-2）。

スキーマ:
    routine_events(id, timestamp, event_type, details, duration_minutes)

`details` カラムは JSON 文字列として保存し、Python 側では dict として扱う。
`event_type` の想定値は 'sleep_start', 'sleep_end', 'meal', 'activity'（DESIGN.md §2-2 参照、
ただし将来拡張のため文字列フィールドのまま維持）。

API:
    RoutineStore(db_path)
    .insert(event_type, details=None, duration_minutes=None, timestamp=None) -> int
    .get(event_id)               -> dict | None    # details は dict にデコード済み
    .list_recent(days=7, limit=100)        -> list[dict]
    .list_by_type(event_type, limit=100)   -> list[dict]
    .list_in_range(start_iso, end_iso, limit=1000) -> list[dict]
    .update(event_id, **fields)  -> bool
    .delete(event_id)            -> bool
    .close() / context manager
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "stores" / "routines.db"

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS routine_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    event_type TEXT NOT NULL,
    details TEXT,
    duration_minutes INTEGER
);
CREATE INDEX IF NOT EXISTS idx_routine_time ON routine_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_routine_type ON routine_events(event_type);
"""

_UPDATABLE_FIELDS = frozenset(
    {
        "timestamp",
        "event_type",
        "details",
        "duration_minutes",
    }
)


def _encode_details(details: dict[str, Any] | None) -> str | None:
    if details is None:
        return None
    return json.dumps(details, ensure_ascii=False, sort_keys=True)


def _decode_details(raw: str | None) -> dict[str, Any] | None:
    if raw is None:
        return None
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError:
        # 壊れた JSON は raw 文字列として { "_raw": ... } で返す（データ損失防止）
        return {"_raw": raw}
    if not isinstance(decoded, dict):
        return {"_raw": raw}
    return decoded


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    record = dict(row)
    record["details"] = _decode_details(record.get("details"))
    return record


class RoutineStore:
    """Persistent store for lifestyle pattern events (F-3)."""

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH) -> None:
        self.db_path = str(db_path)
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA_SQL)
        self._conn.commit()

    def _require_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("RoutineStore is closed")
        return self._conn

    def insert(
        self,
        event_type: str,
        details: dict[str, Any] | None = None,
        duration_minutes: int | None = None,
        timestamp: str | None = None,
    ) -> int:
        if timestamp is None:
            timestamp = datetime.now(timezone.utc).isoformat()
        conn = self._require_conn()
        cur = conn.execute(
            """
            INSERT INTO routine_events
                (timestamp, event_type, details, duration_minutes)
            VALUES (?, ?, ?, ?)
            """,
            (timestamp, event_type, _encode_details(details), duration_minutes),
        )
        conn.commit()
        assert cur.lastrowid is not None
        return cur.lastrowid

    def get(self, event_id: int) -> dict[str, Any] | None:
        conn = self._require_conn()
        row = conn.execute(
            "SELECT * FROM routine_events WHERE id = ?", (event_id,)
        ).fetchone()
        return _row_to_dict(row) if row else None

    def list_recent(self, days: int = 7, limit: int = 100) -> list[dict[str, Any]]:
        conn = self._require_conn()
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        rows = conn.execute(
            """
            SELECT * FROM routine_events
            WHERE timestamp >= ?
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (cutoff, limit),
        ).fetchall()
        return [_row_to_dict(row) for row in rows]

    def list_by_type(self, event_type: str, limit: int = 100) -> list[dict[str, Any]]:
        conn = self._require_conn()
        rows = conn.execute(
            """
            SELECT * FROM routine_events
            WHERE event_type = ?
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (event_type, limit),
        ).fetchall()
        return [_row_to_dict(row) for row in rows]

    def list_in_range(
        self,
        start_iso: str,
        end_iso: str,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        conn = self._require_conn()
        rows = conn.execute(
            """
            SELECT * FROM routine_events
            WHERE timestamp >= ? AND timestamp < ?
            ORDER BY timestamp ASC
            LIMIT ?
            """,
            (start_iso, end_iso, limit),
        ).fetchall()
        return [_row_to_dict(row) for row in rows]

    def update(self, event_id: int, **fields: Any) -> bool:
        invalid = set(fields) - _UPDATABLE_FIELDS
        if invalid:
            raise ValueError(f"Invalid fields: {sorted(invalid)}")
        if not fields:
            return False
        if "details" in fields:
            fields["details"] = _encode_details(fields["details"])
        conn = self._require_conn()
        cols = ", ".join(f"{key} = ?" for key in fields)
        values = list(fields.values()) + [event_id]
        cur = conn.execute(
            f"UPDATE routine_events SET {cols} WHERE id = ?",
            values,
        )
        conn.commit()
        return cur.rowcount > 0

    def delete(self, event_id: int) -> bool:
        conn = self._require_conn()
        cur = conn.execute("DELETE FROM routine_events WHERE id = ?", (event_id,))
        conn.commit()
        return cur.rowcount > 0

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> "RoutineStore":
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()
