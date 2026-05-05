"""kyojuro_memory.lib.stores.symptom_store — F-2 symptom timeline.

DESIGN.md §2-2 の symptoms.db スキーマに準拠した SQLite ストア。
プライバシー絶対、全データローカル（DESIGN.md §1-2）。

スキーマ:
    symptoms(id, timestamp, symptom_type, severity, description,
             concurrent_conditions, resolved_at, treatment)

API:
    SymptomStore(db_path)
    .insert(symptom_type, severity=None, ...) -> int
    .get(symptom_id)              -> dict | None
    .list_recent(days=7, limit=100)        -> list[dict]
    .list_by_type(symptom_type, limit=100) -> list[dict]
    .list_unresolved(limit=100)            -> list[dict]
    .resolve(symptom_id, resolved_at=None, treatment=None) -> bool
    .update(symptom_id, **fields) -> bool
    .delete(symptom_id)           -> bool
    .close() / context manager
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "stores" / "symptoms.db"

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS symptoms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    symptom_type TEXT NOT NULL,
    severity INTEGER,
    description TEXT,
    concurrent_conditions TEXT,
    resolved_at TEXT,
    treatment TEXT
);
CREATE INDEX IF NOT EXISTS idx_symptom_time ON symptoms(timestamp);
CREATE INDEX IF NOT EXISTS idx_symptom_type ON symptoms(symptom_type);
"""

_UPDATABLE_FIELDS = frozenset(
    {
        "timestamp",
        "symptom_type",
        "severity",
        "description",
        "concurrent_conditions",
        "resolved_at",
        "treatment",
    }
)


def _validate_severity(severity: int | None) -> None:
    if severity is None:
        return
    if not isinstance(severity, int):
        raise TypeError(f"severity must be int or None, got {type(severity).__name__}")
    if not 1 <= severity <= 10:
        raise ValueError(f"severity must be in 1..10, got {severity}")


class SymptomStore:
    """Persistent store for symptom records (F-2)."""

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
            raise RuntimeError("SymptomStore is closed")
        return self._conn

    def insert(
        self,
        symptom_type: str,
        severity: int | None = None,
        timestamp: str | None = None,
        description: str | None = None,
        concurrent_conditions: str | None = None,
        resolved_at: str | None = None,
        treatment: str | None = None,
    ) -> int:
        _validate_severity(severity)
        if timestamp is None:
            timestamp = datetime.now(timezone.utc).isoformat()
        conn = self._require_conn()
        cur = conn.execute(
            """
            INSERT INTO symptoms
                (timestamp, symptom_type, severity, description,
                 concurrent_conditions, resolved_at, treatment)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                timestamp,
                symptom_type,
                severity,
                description,
                concurrent_conditions,
                resolved_at,
                treatment,
            ),
        )
        conn.commit()
        assert cur.lastrowid is not None
        return cur.lastrowid

    def get(self, symptom_id: int) -> dict[str, Any] | None:
        conn = self._require_conn()
        row = conn.execute(
            "SELECT * FROM symptoms WHERE id = ?", (symptom_id,)
        ).fetchone()
        return dict(row) if row else None

    def list_recent(self, days: int = 7, limit: int = 100) -> list[dict[str, Any]]:
        conn = self._require_conn()
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        rows = conn.execute(
            """
            SELECT * FROM symptoms
            WHERE timestamp >= ?
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (cutoff, limit),
        ).fetchall()
        return [dict(row) for row in rows]

    def list_by_type(self, symptom_type: str, limit: int = 100) -> list[dict[str, Any]]:
        conn = self._require_conn()
        rows = conn.execute(
            """
            SELECT * FROM symptoms
            WHERE symptom_type = ?
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (symptom_type, limit),
        ).fetchall()
        return [dict(row) for row in rows]

    def list_unresolved(self, limit: int = 100) -> list[dict[str, Any]]:
        conn = self._require_conn()
        rows = conn.execute(
            """
            SELECT * FROM symptoms
            WHERE resolved_at IS NULL
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]

    def resolve(
        self,
        symptom_id: int,
        resolved_at: str | None = None,
        treatment: str | None = None,
    ) -> bool:
        if resolved_at is None:
            resolved_at = datetime.now(timezone.utc).isoformat()
        fields: dict[str, Any] = {"resolved_at": resolved_at}
        if treatment is not None:
            fields["treatment"] = treatment
        return self.update(symptom_id, **fields)

    def update(self, symptom_id: int, **fields: Any) -> bool:
        invalid = set(fields) - _UPDATABLE_FIELDS
        if invalid:
            raise ValueError(f"Invalid fields: {sorted(invalid)}")
        if not fields:
            return False
        if "severity" in fields:
            _validate_severity(fields["severity"])
        conn = self._require_conn()
        cols = ", ".join(f"{key} = ?" for key in fields)
        values = list(fields.values()) + [symptom_id]
        cur = conn.execute(
            f"UPDATE symptoms SET {cols} WHERE id = ?",
            values,
        )
        conn.commit()
        return cur.rowcount > 0

    def delete(self, symptom_id: int) -> bool:
        conn = self._require_conn()
        cur = conn.execute("DELETE FROM symptoms WHERE id = ?", (symptom_id,))
        conn.commit()
        return cur.rowcount > 0

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> "SymptomStore":
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()
