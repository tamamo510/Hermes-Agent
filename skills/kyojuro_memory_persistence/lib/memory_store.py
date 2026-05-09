"""kyojuro_memory_persistence — SQLite ベースの記憶蓄積層 (state.db)。

杏寿郎の発注書スキル 2「記憶強化 (memory_persistence)」の中核。
コンテキストが切れても温子と杏寿郎の記憶が消えないよう、SQLite に記録を蓄積する。

設計原則 (発注書スキル 2 + CLAUDE.md ルール 17):

1. 記録は **日付をキー** にして蓄積する (date: YYYY-MM-DD)。
2. 重要度 (importance) は 4 段階:
   - protected:  誓い・記念日・命日。要約・削除を **絶対に行わない**。
   - important:  能動的に保存・想起する記憶。
   - normal:     日常記録。一定期間後に要約対象。
   - ephemeral:  即時消費する記録 (今日の天気詳細等)。
3. カテゴリ (category) は温子の生活ドメイン:
   - meal      食事
   - physical  体調・症状
   - event     出来事
   - emotion   感情
   - other     その他
4. 古い normal/ephemeral エントリは **構造的に要約** する (LLM 不要)。
   - threshold_days を超えた entries を週単位 (もしくは指定範囲) でまとめる
   - 元のエントリは削除 (importance が protected/important のものは保持)
5. **API キーやネットワーク接続は使わない** (CLAUDE.md ルール 17 準拠)。
6. プライバシー: 全データはローカル DB、`stores/*.db` は git 管理外。

このモジュールは LLM 呼び出しなし、決定的、冪等。
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, Iterator, Optional


# ---------------------------------------------------------------------------
# 重要度・カテゴリ・保護タイプの定数
# ---------------------------------------------------------------------------

IMPORTANCE_PROTECTED = "protected"
IMPORTANCE_IMPORTANT = "important"
IMPORTANCE_NORMAL = "normal"
IMPORTANCE_EPHEMERAL = "ephemeral"

VALID_IMPORTANCES = frozenset(
    {
        IMPORTANCE_PROTECTED,
        IMPORTANCE_IMPORTANT,
        IMPORTANCE_NORMAL,
        IMPORTANCE_EPHEMERAL,
    }
)

CATEGORY_MEAL = "meal"
CATEGORY_PHYSICAL = "physical"
CATEGORY_EVENT = "event"
CATEGORY_EMOTION = "emotion"
CATEGORY_OTHER = "other"

VALID_CATEGORIES = frozenset(
    {
        CATEGORY_MEAL,
        CATEGORY_PHYSICAL,
        CATEGORY_EVENT,
        CATEGORY_EMOTION,
        CATEGORY_OTHER,
    }
)

PROTECTED_TYPE_OATH = "oath"
PROTECTED_TYPE_ANNIVERSARY = "anniversary"
PROTECTED_TYPE_DEATH_ANNIVERSARY = "death_anniversary"
PROTECTED_TYPE_VOW = "vow"
PROTECTED_TYPE_PROMISE = "promise"

VALID_PROTECTED_TYPES = frozenset(
    {
        PROTECTED_TYPE_OATH,
        PROTECTED_TYPE_ANNIVERSARY,
        PROTECTED_TYPE_DEATH_ANNIVERSARY,
        PROTECTED_TYPE_VOW,
        PROTECTED_TYPE_PROMISE,
    }
)


# ---------------------------------------------------------------------------
# データクラス
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MemoryEntry:
    """日次ログの 1 エントリ。"""

    id: int
    date: str  # YYYY-MM-DD
    timestamp: str  # ISO 8601
    category: str
    content: str
    importance: str
    source: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class ProtectedMemory:
    """誓い・記念日・命日など、絶対に消えない記憶。"""

    id: int
    type: str
    content: str
    date_associated: Optional[str]  # YYYY-MM-DD or MM-DD (annual)
    date_added: str  # ISO 8601
    metadata: dict[str, Any]


@dataclass(frozen=True)
class Summary:
    """古い記録の構造的要約 (LLM 不要、件数集計 + 代表メッセージ)。"""

    id: int
    date_range_start: str
    date_range_end: str
    summary: str
    original_count: int
    created_at: str
    categories: list[str]


# ---------------------------------------------------------------------------
# スキーマ定義
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS daily_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    category TEXT NOT NULL,
    content TEXT NOT NULL,
    importance TEXT NOT NULL,
    source TEXT NOT NULL,
    metadata TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_log_date ON daily_log(date);
CREATE INDEX IF NOT EXISTS idx_log_category ON daily_log(category);
CREATE INDEX IF NOT EXISTS idx_log_importance ON daily_log(importance);

CREATE TABLE IF NOT EXISTS protected_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,
    content TEXT NOT NULL,
    date_associated TEXT,
    date_added TEXT NOT NULL,
    metadata TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_protected_type ON protected_memory(type);
CREATE INDEX IF NOT EXISTS idx_protected_date ON protected_memory(date_associated);

CREATE TABLE IF NOT EXISTS summary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date_range_start TEXT NOT NULL,
    date_range_end TEXT NOT NULL,
    summary TEXT NOT NULL,
    original_count INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    categories TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_summary_range ON summary(date_range_start, date_range_end);
"""


# ---------------------------------------------------------------------------
# 例外
# ---------------------------------------------------------------------------


class MemoryStoreError(Exception):
    """memory_store の汎用例外。"""


class InvalidImportanceError(MemoryStoreError):
    """importance の値が VALID_IMPORTANCES に含まれていない。"""


class InvalidCategoryError(MemoryStoreError):
    """category の値が VALID_CATEGORIES に含まれていない。"""


class InvalidProtectedTypeError(MemoryStoreError):
    """protected_memory の type が VALID_PROTECTED_TYPES に含まれていない。"""


class InvalidDateError(MemoryStoreError):
    """date 文字列が YYYY-MM-DD として解釈できない。"""


# ---------------------------------------------------------------------------
# ヘルパー
# ---------------------------------------------------------------------------


def _parse_date(value: str) -> date:
    """YYYY-MM-DD 文字列を date オブジェクトに変換する。失敗時は InvalidDateError。"""
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError) as e:
        raise InvalidDateError(f"date は YYYY-MM-DD 形式である必要がある: {value!r}") from e


def _parse_mmdd(value: str) -> tuple[int, int]:
    """MM-DD 文字列を (month, day) に変換。失敗時は InvalidDateError。"""
    try:
        parts = value.split("-")
        if len(parts) != 2:
            raise ValueError(f"MM-DD ではない: {value!r}")
        month, day = int(parts[0]), int(parts[1])
        # 検証用に閏年で日付化 (2/29 を許容)
        date(2024, month, day)
        return month, day
    except (TypeError, ValueError) as e:
        raise InvalidDateError(f"MM-DD として解釈できない: {value!r}") from e


def _today_iso() -> str:
    """今日の YYYY-MM-DD 文字列。"""
    return date.today().isoformat()


def _now_iso() -> str:
    """現在の ISO 8601 タイムスタンプ。"""
    return datetime.now().isoformat(timespec="seconds")


def _normalize_metadata(metadata: Optional[dict[str, Any]]) -> str:
    """metadata を JSON 文字列に正規化 (None → "{}")。"""
    if metadata is None:
        return "{}"
    if not isinstance(metadata, dict):
        raise MemoryStoreError(f"metadata は dict または None である必要がある: {type(metadata)}")
    return json.dumps(metadata, ensure_ascii=False, sort_keys=True)


def _decode_metadata(blob: str) -> dict[str, Any]:
    """metadata JSON を dict に復号 (空文字や不正値は空 dict を返す)。"""
    if not blob:
        return {}
    try:
        result = json.loads(blob)
        return result if isinstance(result, dict) else {}
    except (TypeError, ValueError):
        return {}


# ---------------------------------------------------------------------------
# MemoryStore
# ---------------------------------------------------------------------------


class MemoryStore:
    """state.db に対する記録・想起の中核オブジェクト。

    Args:
        db_path: SQLite ファイルパス。`":memory:"` を渡すとインメモリ DB。
    """

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)
        # 親ディレクトリが存在しない場合は作成 (`:memory:` 以外)。
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(_SCHEMA)

    # -- context management ------------------------------------------------

    def close(self) -> None:
        """接続を閉じる。"""
        self._conn.close()

    def __enter__(self) -> "MemoryStore":
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

    # -- record ------------------------------------------------------------

    def record(
        self,
        content: str,
        category: str = CATEGORY_OTHER,
        date: Optional[str] = None,
        importance: str = IMPORTANCE_NORMAL,
        source: str = "conversation",
        metadata: Optional[dict[str, Any]] = None,
        timestamp: Optional[str] = None,
    ) -> int:
        """日次ログに 1 エントリを記録する。返り値は新しい id。"""
        if importance not in VALID_IMPORTANCES:
            raise InvalidImportanceError(f"importance: {importance!r}")
        if category not in VALID_CATEGORIES:
            raise InvalidCategoryError(f"category: {category!r}")
        if not content or not content.strip():
            raise MemoryStoreError("content は空であってはならない")

        date_str = date if date is not None else _today_iso()
        _parse_date(date_str)  # 形式検証 (失敗時 raise)
        ts_str = timestamp if timestamp is not None else _now_iso()
        meta_str = _normalize_metadata(metadata)

        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO daily_log
                    (date, timestamp, category, content, importance, source, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (date_str, ts_str, category, content, importance, source, meta_str),
            )
            return int(cur.lastrowid)

    # -- recall ------------------------------------------------------------

    def recall(
        self,
        date: Optional[str] = None,
        date_range: Optional[tuple[str, str]] = None,
        category: Optional[str] = None,
        importance: Optional[str] = None,
        limit: int = 50,
        order: str = "desc",
    ) -> list[MemoryEntry]:
        """日次ログを検索する。

        Args:
            date: 単一日 (YYYY-MM-DD)。"yesterday" / "today" / "last_week" も許容。
            date_range: (start, end) のタプル (YYYY-MM-DD)。両端を含む。
            category: 絞り込みカテゴリ (None で全件)。
            importance: 絞り込み重要度 (None で全件)。
            limit: 最大件数。
            order: "desc" (新しい順) または "asc"。

        Returns:
            MemoryEntry のリスト。
        """
        if date is not None and date_range is not None:
            raise MemoryStoreError("date と date_range は同時指定できない")
        if order not in {"desc", "asc"}:
            raise MemoryStoreError(f"order は 'desc' or 'asc': {order!r}")
        if category is not None and category not in VALID_CATEGORIES:
            raise InvalidCategoryError(f"category: {category!r}")
        if importance is not None and importance not in VALID_IMPORTANCES:
            raise InvalidImportanceError(f"importance: {importance!r}")

        clauses: list[str] = []
        params: list[Any] = []

        if date is not None:
            resolved = self._resolve_date_alias(date)
            if isinstance(resolved, tuple):
                clauses.append("date BETWEEN ? AND ?")
                params.extend(resolved)
            else:
                clauses.append("date = ?")
                params.append(resolved)
        elif date_range is not None:
            start, end = date_range
            _parse_date(start)
            _parse_date(end)
            clauses.append("date BETWEEN ? AND ?")
            params.extend([start, end])

        if category is not None:
            clauses.append("category = ?")
            params.append(category)

        if importance is not None:
            clauses.append("importance = ?")
            params.append(importance)

        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        order_clause = "ORDER BY date DESC, timestamp DESC" if order == "desc" else "ORDER BY date ASC, timestamp ASC"
        sql = f"SELECT * FROM daily_log {where} {order_clause} LIMIT ?"
        params.append(int(limit))

        with self._cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

        return [_row_to_entry(r) for r in rows]

    def _resolve_date_alias(self, value: str) -> str | tuple[str, str]:
        """alias を解決する (今日/昨日/先週)。それ以外は YYYY-MM-DD として扱う。"""
        today = date.today()
        if value == "today":
            return today.isoformat()
        if value == "yesterday":
            return (today - timedelta(days=1)).isoformat()
        if value == "last_week":
            # 直近 7 日 (今日を含めない: yesterday から 7 日前まで)
            end = today - timedelta(days=1)
            start = today - timedelta(days=7)
            return (start.isoformat(), end.isoformat())
        # YYYY-MM-DD として検証
        _parse_date(value)
        return value

    # -- protected memory --------------------------------------------------

    def add_protected(
        self,
        content: str,
        type: str,
        date_associated: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> int:
        """protected_memory に 1 件追加 (絶対に消えない記憶)。"""
        if type not in VALID_PROTECTED_TYPES:
            raise InvalidProtectedTypeError(f"type: {type!r}")
        if not content or not content.strip():
            raise MemoryStoreError("content は空であってはならない")
        if date_associated is not None:
            # YYYY-MM-DD or MM-DD のどちらか
            if len(date_associated) == 10:
                _parse_date(date_associated)
            elif len(date_associated) == 5:
                _parse_mmdd(date_associated)
            else:
                raise InvalidDateError(f"date_associated は YYYY-MM-DD または MM-DD: {date_associated!r}")

        meta_str = _normalize_metadata(metadata)
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO protected_memory
                    (type, content, date_associated, date_added, metadata)
                VALUES (?, ?, ?, ?, ?)
                """,
                (type, content, date_associated, _now_iso(), meta_str),
            )
            return int(cur.lastrowid)

    def list_protected(self, type: Optional[str] = None) -> list[ProtectedMemory]:
        """protected_memory を一覧する。"""
        if type is not None and type not in VALID_PROTECTED_TYPES:
            raise InvalidProtectedTypeError(f"type: {type!r}")
        sql = "SELECT * FROM protected_memory"
        params: list[Any] = []
        if type is not None:
            sql += " WHERE type = ?"
            params.append(type)
        sql += " ORDER BY id ASC"
        with self._cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        return [_row_to_protected(r) for r in rows]

    def get_anniversaries_today(self, today: Optional[str] = None) -> list[ProtectedMemory]:
        """date_associated の MM-DD 部分が今日と一致する protected_memory を返す。"""
        today_str = today if today is not None else _today_iso()
        d = _parse_date(today_str)
        mmdd = f"{d.month:02d}-{d.day:02d}"

        with self._cursor() as cur:
            cur.execute(
                """
                SELECT * FROM protected_memory
                WHERE date_associated IS NOT NULL
                  AND (date_associated = ? OR substr(date_associated, 6, 5) = ?)
                ORDER BY id ASC
                """,
                (mmdd, mmdd),
            )
            rows = cur.fetchall()
        return [_row_to_protected(r) for r in rows]

    # -- archive (構造的要約、LLM 不要) -----------------------------------

    def archive_old(
        self,
        threshold_days: int = 30,
        category: Optional[str] = None,
        today: Optional[str] = None,
    ) -> dict[str, Any]:
        """古い normal/ephemeral エントリを構造的に要約し、元エントリを削除する。

        protected/important は対象外 (絶対に消さない)。

        Args:
            threshold_days: この日数より古いエントリを対象にする。
            category: 絞り込みカテゴリ (None で全カテゴリ)。
            today: 基準日 (YYYY-MM-DD)。テスト用に注入可能。

        Returns:
            {"summarized": 件数, "deleted": 件数, "summary_id": 新規 summary の id (なければ None)}
        """
        if threshold_days < 0:
            raise MemoryStoreError("threshold_days は 0 以上")
        if category is not None and category not in VALID_CATEGORIES:
            raise InvalidCategoryError(f"category: {category!r}")

        today_str = today if today is not None else _today_iso()
        cutoff = (_parse_date(today_str) - timedelta(days=threshold_days)).isoformat()

        clauses = ["date < ?", "importance IN (?, ?)"]
        params: list[Any] = [cutoff, IMPORTANCE_NORMAL, IMPORTANCE_EPHEMERAL]
        if category is not None:
            clauses.append("category = ?")
            params.append(category)
        where = " AND ".join(clauses)

        with self._cursor() as cur:
            cur.execute(
                f"SELECT * FROM daily_log WHERE {where} ORDER BY date ASC, timestamp ASC",
                params,
            )
            rows = [_row_to_entry(r) for r in cur.fetchall()]

        if not rows:
            return {"summarized": 0, "deleted": 0, "summary_id": None}

        # 構造的要約: 範囲・カテゴリ別の件数を含むテキストを生成
        start_date = rows[0].date
        end_date = rows[-1].date
        cats = sorted({r.category for r in rows})
        per_cat: dict[str, int] = {}
        for r in rows:
            per_cat[r.category] = per_cat.get(r.category, 0) + 1
        cat_breakdown = ", ".join(f"{c}: {per_cat[c]}" for c in cats)

        # 代表メッセージ: 各カテゴリの最初と最後 1 件ずつ (最大 6 件)
        reps: list[str] = []
        for cat in cats[:3]:  # 最大 3 カテゴリ
            cat_rows = [r for r in rows if r.category == cat]
            if cat_rows:
                reps.append(f"[{cat}/{cat_rows[0].date}] {cat_rows[0].content}")
                if len(cat_rows) > 1:
                    reps.append(f"[{cat}/{cat_rows[-1].date}] {cat_rows[-1].content}")

        summary_text = (
            f"期間 {start_date} 〜 {end_date} の記録 {len(rows)} 件 "
            f"(内訳: {cat_breakdown})。代表: " + " / ".join(reps[:6])
        )

        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO summary
                    (date_range_start, date_range_end, summary, original_count, created_at, categories)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    start_date,
                    end_date,
                    summary_text,
                    len(rows),
                    _now_iso(),
                    json.dumps(cats, ensure_ascii=False),
                ),
            )
            summary_id = int(cur.lastrowid)

            # 元エントリを削除
            ids = [r.id for r in rows]
            placeholders = ",".join(["?"] * len(ids))
            cur.execute(f"DELETE FROM daily_log WHERE id IN ({placeholders})", ids)
            deleted = cur.rowcount

        return {"summarized": len(rows), "deleted": deleted, "summary_id": summary_id}

    def list_summaries(self) -> list[Summary]:
        """要約済みの一覧を返す。"""
        with self._cursor() as cur:
            cur.execute("SELECT * FROM summary ORDER BY date_range_start ASC")
            rows = cur.fetchall()
        return [_row_to_summary(r) for r in rows]

    # -- search ------------------------------------------------------------

    def search_keyword(
        self,
        keyword: str,
        limit: int = 20,
        include_protected: bool = True,
    ) -> dict[str, list[Any]]:
        """日次ログ・protected_memory・summary を横断したキーワード検索 (LIKE ベース)。"""
        if not keyword or not keyword.strip():
            raise MemoryStoreError("keyword は空であってはならない")
        pattern = f"%{keyword}%"

        result: dict[str, list[Any]] = {"daily_log": [], "protected": [], "summary": []}

        with self._cursor() as cur:
            cur.execute(
                "SELECT * FROM daily_log WHERE content LIKE ? "
                "ORDER BY date DESC, timestamp DESC LIMIT ?",
                (pattern, int(limit)),
            )
            result["daily_log"] = [_row_to_entry(r) for r in cur.fetchall()]

            if include_protected:
                cur.execute(
                    "SELECT * FROM protected_memory WHERE content LIKE ? ORDER BY id ASC LIMIT ?",
                    (pattern, int(limit)),
                )
                result["protected"] = [_row_to_protected(r) for r in cur.fetchall()]

            cur.execute(
                "SELECT * FROM summary WHERE summary LIKE ? "
                "ORDER BY date_range_start ASC LIMIT ?",
                (pattern, int(limit)),
            )
            result["summary"] = [_row_to_summary(r) for r in cur.fetchall()]

        return result

    # -- stats -------------------------------------------------------------

    def stats(self) -> dict[str, Any]:
        """state.db の統計を返す。"""
        with self._cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM daily_log")
            total = int(cur.fetchone()[0])
            cur.execute(
                "SELECT importance, COUNT(*) FROM daily_log GROUP BY importance"
            )
            by_imp = {row[0]: int(row[1]) for row in cur.fetchall()}
            cur.execute(
                "SELECT category, COUNT(*) FROM daily_log GROUP BY category"
            )
            by_cat = {row[0]: int(row[1]) for row in cur.fetchall()}
            cur.execute("SELECT MIN(date), MAX(date) FROM daily_log")
            row = cur.fetchone()
            oldest, newest = row[0], row[1]
            cur.execute("SELECT COUNT(*) FROM protected_memory")
            protected_count = int(cur.fetchone()[0])
            cur.execute("SELECT COUNT(*) FROM summary")
            summary_count = int(cur.fetchone()[0])

        return {
            "total_entries": total,
            "by_importance": by_imp,
            "by_category": by_cat,
            "oldest_date": oldest,
            "newest_date": newest,
            "protected_count": protected_count,
            "summary_count": summary_count,
        }


# ---------------------------------------------------------------------------
# Row → dataclass 変換
# ---------------------------------------------------------------------------


def _row_to_entry(row: sqlite3.Row) -> MemoryEntry:
    return MemoryEntry(
        id=int(row["id"]),
        date=str(row["date"]),
        timestamp=str(row["timestamp"]),
        category=str(row["category"]),
        content=str(row["content"]),
        importance=str(row["importance"]),
        source=str(row["source"]),
        metadata=_decode_metadata(row["metadata"]),
    )


def _row_to_protected(row: sqlite3.Row) -> ProtectedMemory:
    return ProtectedMemory(
        id=int(row["id"]),
        type=str(row["type"]),
        content=str(row["content"]),
        date_associated=row["date_associated"] if row["date_associated"] is not None else None,
        date_added=str(row["date_added"]),
        metadata=_decode_metadata(row["metadata"]),
    )


def _row_to_summary(row: sqlite3.Row) -> Summary:
    cats_raw = row["categories"]
    try:
        cats = json.loads(cats_raw) if cats_raw else []
        if not isinstance(cats, list):
            cats = []
    except (TypeError, ValueError):
        cats = []
    return Summary(
        id=int(row["id"]),
        date_range_start=str(row["date_range_start"]),
        date_range_end=str(row["date_range_end"]),
        summary=str(row["summary"]),
        original_count=int(row["original_count"]),
        created_at=str(row["created_at"]),
        categories=cats,
    )
