"""kyojuro_memory.lib.stores.supplement_store — F-1 supplement intake records.

DESIGN.md §2-2 の supplements.db スキーマに準拠した SQLite ストア。
プライバシー絶対、全データローカル（DESIGN.md §1-2）。本クラスは外部送信を一切行わない。

スキーマ:
    supplement_intakes(id, timestamp, supplement_name, dose, context,
                       felt_effect, extracted_from_message_id)

API:
    SupplementStore(db_path)         接続を開きスキーマを idempotent に作成
    .insert(supplement_name, ...) -> int     新規レコード、返り値は id
    .get(intake_id)               -> dict | None
    .list_recent(days=7, limit=100) -> list[dict]
    .list_by_name(name, limit=100)  -> list[dict]
    .update(intake_id, **fields)   -> bool
    .delete(intake_id)             -> bool
    .close() / context manager (with 文対応)
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "stores" / "supplements.db"

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS supplement_intakes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    supplement_name TEXT NOT NULL,
    dose TEXT,
    context TEXT,
    felt_effect TEXT,
    extracted_from_message_id TEXT
);
CREATE INDEX IF NOT EXISTS idx_supplement_time ON supplement_intakes(timestamp);
CREATE INDEX IF NOT EXISTS idx_supplement_name ON supplement_intakes(supplement_name);
"""

_UPDATABLE_FIELDS = frozenset(
    {
        "timestamp",
        "supplement_name",
        "dose",
        "context",
        "felt_effect",
        "extracted_from_message_id",
    }
)


class SupplementStore:
    """Persistent store for supplement intake records (F-1)."""

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
            raise RuntimeError("SupplementStore is closed")
        return self._conn

    def insert(
        self,
        supplement_name: str,
        timestamp: str | None = None,
        dose: str | None = None,
        context: str | None = None,
        felt_effect: str | None = None,
        extracted_from_message_id: str | None = None,
    ) -> int:
        if timestamp is None:
            timestamp = datetime.now(timezone.utc).isoformat()
        conn = self._require_conn()
        cur = conn.execute(
            """
            INSERT INTO supplement_intakes
                (timestamp, supplement_name, dose, context, felt_effect, extracted_from_message_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (timestamp, supplement_name, dose, context, felt_effect, extracted_from_message_id),
        )
        conn.commit()
        assert cur.lastrowid is not None
        return cur.lastrowid

    def get(self, intake_id: int) -> dict[str, Any] | None:
        conn = self._require_conn()
        row = conn.execute(
            "SELECT * FROM supplement_intakes WHERE id = ?", (intake_id,)
        ).fetchone()
        return dict(row) if row else None

    def list_recent(self, days: int = 7, limit: int = 100) -> list[dict[str, Any]]:
        conn = self._require_conn()
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        rows = conn.execute(
            """
            SELECT * FROM supplement_intakes
            WHERE timestamp >= ?
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (cutoff, limit),
        ).fetchall()
        return [dict(row) for row in rows]

    def list_by_name(self, name: str, limit: int = 100) -> list[dict[str, Any]]:
        conn = self._require_conn()
        rows = conn.execute(
            """
            SELECT * FROM supplement_intakes
            WHERE supplement_name = ?
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (name, limit),
        ).fetchall()
        return [dict(row) for row in rows]

    def update(self, intake_id: int, **fields: Any) -> bool:
        invalid = set(fields) - _UPDATABLE_FIELDS
        if invalid:
            raise ValueError(f"Invalid fields: {sorted(invalid)}")
        if not fields:
            return False
        conn = self._require_conn()
        cols = ", ".join(f"{key} = ?" for key in fields)
        values = list(fields.values()) + [intake_id]
        cur = conn.execute(
            f"UPDATE supplement_intakes SET {cols} WHERE id = ?",
            values,
        )
        conn.commit()
        return cur.rowcount > 0

    def delete(self, intake_id: int) -> bool:
        conn = self._require_conn()
        cur = conn.execute("DELETE FROM supplement_intakes WHERE id = ?", (intake_id,))
        conn.commit()
        return cur.rowcount > 0

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> "SupplementStore":
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()
