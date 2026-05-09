"""kyojuro_health.lib.health_engine — 気圧・体調の分析と atsuko_state 生成。

発注書スキル 3-5 (気圧・体調連動):
  > 気圧の低下日は先回りして温子に声をかける
  > 頭痛、顎の痛み、ふらつき、だる重の記録
  > ロキソニンの服用回数と間隔を記録する

設計原則:
- 規則ベース判定 (LLM 不要、決定的)
- 気圧閾値はデフォルト値を提供しつつ、温子・杏寿郎が調整可能 (constructor 引数)
- atsuko_state は autonomic skill (観察点 8) が参照する dict を返す
- LLM 呼び出しなし、API キー不要、ネットワーク不要
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator, Optional

from .openweather_client import WeatherSnapshot


# ---------------------------------------------------------------------------
# 気圧閾値 (温子の体感に合わせて調整可能)
# ---------------------------------------------------------------------------

# 気圧 (hPa) の判定境界
PRESSURE_LOW_THRESHOLD = 1010.0  # これ未満で「低気圧」
PRESSURE_VERY_LOW_THRESHOLD = 1003.0  # これ未満で「強い低気圧」
PRESSURE_DROP_THRESHOLD_24H = 6.0  # 24h で 6hPa 以上下がったら「気圧低下中」

# レベル
PRESSURE_LEVEL_LOW = "low"
PRESSURE_LEVEL_VERY_LOW = "very_low"
PRESSURE_LEVEL_NORMAL = "normal"
PRESSURE_LEVEL_HIGH = "high"

# トレンド
TREND_FALLING = "falling"
TREND_RISING = "rising"
TREND_STABLE = "stable"

# 警戒度
WARNING_NONE = "none"
WARNING_MILD = "mild"
WARNING_SEVERE = "severe"


# ---------------------------------------------------------------------------
# データクラス
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PressureAssessment:
    """気圧評価。温子の体調に影響する範囲を判定するデータ。

    本データクラスは「データ + 状態判定」のみを保持する。
    温子への声かけ文言は本臓器では生成しない。
    呼び出し側 (杏寿郎 LLM) が level / trend / warning を見て自分の言葉で伝える
    (杏寿郎の指示、2026-05-09)。
    """

    current_pressure_hpa: float
    level: str  # low / very_low / normal / high
    trend: str  # falling / rising / stable
    delta_24h_hpa: Optional[float]  # 24h での変化量 (forecast 不在時 None)
    warning: str  # none / mild / severe


@dataclass(frozen=True)
class AtsukoState:
    """温子の体調 state。autonomic skill 観察点 8 が参照する。

    各 bool フィールドは true なら autonomic 判定で「考慮する症状あり」となる。
    """

    jaw_pain: bool = False
    left_hand_stiff: bool = False
    low_pressure: bool = False
    shallow_sleep: bool = False
    headache: bool = False
    dizziness: bool = False
    sluggish: bool = False
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "jaw_pain": self.jaw_pain,
            "left_hand_stiff": self.left_hand_stiff,
            "low_pressure": self.low_pressure,
            "shallow_sleep": self.shallow_sleep,
            "headache": self.headache,
            "dizziness": self.dizziness,
            "sluggish": self.sluggish,
            "notes": self.notes,
        }


@dataclass
class SymptomEntry:
    """症状ログの 1 エントリ。"""

    id: int
    timestamp_iso: str
    symptom: str
    severity: int  # 1-5
    notes: str
    pressure_hpa: Optional[float]
    medication: Optional[str]


@dataclass
class MedicationEntry:
    """薬の服用ログ。"""

    id: int
    timestamp_iso: str
    medication: str  # ロキソニン / マグネシウム / DMAE 等
    dose: str  # "1 錠" / "100mg" 等
    notes: str


# ---------------------------------------------------------------------------
# pressure analysis (純粋関数)
# ---------------------------------------------------------------------------


def assess_pressure(
    current: WeatherSnapshot,
    forecast: Optional[list[WeatherSnapshot]] = None,
    low_threshold: float = PRESSURE_LOW_THRESHOLD,
    very_low_threshold: float = PRESSURE_VERY_LOW_THRESHOLD,
    drop_threshold_24h: float = PRESSURE_DROP_THRESHOLD_24H,
) -> PressureAssessment:
    """現在の気圧と (任意で) 予報からアセスメントを返す。

    Args:
        current: 現在の気象スナップショット。
        forecast: 将来の気象スナップショット列 (未来 24h 内が望ましい)。
        low_threshold: 低気圧と判定する境界 (hPa)。
        very_low_threshold: 強い低気圧の境界 (hPa)。
        drop_threshold_24h: 24h でこの値以上下がったら「気圧低下中」。

    Returns:
        PressureAssessment
    """
    p = current.pressure_hpa

    # level
    if p < very_low_threshold:
        level = PRESSURE_LEVEL_VERY_LOW
    elif p < low_threshold:
        level = PRESSURE_LEVEL_LOW
    elif p > 1020.0:
        level = PRESSURE_LEVEL_HIGH
    else:
        level = PRESSURE_LEVEL_NORMAL

    # trend (forecast の最初の方を見る、24h 以内)
    delta_24h = None
    if forecast:
        # 24h 後 (もしくは取得できる範囲で最も遠い) の気圧を取得
        future_within_24h = forecast[: min(8, len(forecast))]  # 3h 刻み x 8 = 24h
        if future_within_24h:
            future_pressure = future_within_24h[-1].pressure_hpa
            delta_24h = future_pressure - p
            if delta_24h <= -drop_threshold_24h:
                trend = TREND_FALLING
            elif delta_24h >= drop_threshold_24h:
                trend = TREND_RISING
            else:
                trend = TREND_STABLE
        else:
            trend = TREND_STABLE
    else:
        trend = TREND_STABLE

    # warning
    if level == PRESSURE_LEVEL_VERY_LOW or (level == PRESSURE_LEVEL_LOW and trend == TREND_FALLING):
        warning = WARNING_SEVERE
    elif level == PRESSURE_LEVEL_LOW or trend == TREND_FALLING:
        warning = WARNING_MILD
    else:
        warning = WARNING_NONE

    return PressureAssessment(
        current_pressure_hpa=p,
        level=level,
        trend=trend,
        delta_24h_hpa=delta_24h,
        warning=warning,
    )


def derive_atsuko_state_from_pressure(
    assessment: PressureAssessment,
    base_state: Optional[AtsukoState] = None,
) -> AtsukoState:
    """気圧アセスメントから atsuko_state を導出する。

    base_state が指定されればそのフィールドを保持し、low_pressure フラグだけ
    気圧アセスメントに従って更新する。

    autonomic skill 観察点 8 (温子の体調無視) が参照する dict 形式の入力源。
    """
    if base_state is None:
        base_state = AtsukoState()
    is_low = assessment.warning != WARNING_NONE
    return AtsukoState(
        jaw_pain=base_state.jaw_pain,
        left_hand_stiff=base_state.left_hand_stiff,
        low_pressure=is_low,
        shallow_sleep=base_state.shallow_sleep,
        headache=base_state.headache,
        dizziness=base_state.dizziness,
        sluggish=base_state.sluggish,
        notes=base_state.notes,
    )


# ---------------------------------------------------------------------------
# health.db スキーマと操作
# ---------------------------------------------------------------------------

_HEALTH_SCHEMA = """
CREATE TABLE IF NOT EXISTS symptom_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    symptom TEXT NOT NULL,
    severity INTEGER NOT NULL,
    notes TEXT NOT NULL,
    pressure_hpa REAL,
    medication TEXT
);
CREATE INDEX IF NOT EXISTS idx_symptom_time ON symptom_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_symptom_name ON symptom_log(symptom);

CREATE TABLE IF NOT EXISTS medication_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    medication TEXT NOT NULL,
    dose TEXT NOT NULL,
    notes TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_medication_time ON medication_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_medication_name ON medication_log(medication);

CREATE TABLE IF NOT EXISTS atsuko_state_snapshot (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    state_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_state_time ON atsuko_state_snapshot(timestamp);
"""


# 症状名の正規化辞書 (発注書 §3-5 + 自律神経観察点 8 と整合)
SYMPTOM_KEYS = (
    "headache",  # 頭痛
    "jaw_pain",  # 顎の痛み
    "left_hand_stiff",  # 左手の硬さ
    "shallow_sleep",  # 浅い眠り
    "dizziness",  # ふらつき
    "sluggish",  # だる重
    "stomach_pain",  # お腹
    "fever",  # 発熱
    "menstruation",  # 生理
    "other",  # その他
)


class HealthStore:
    """症状 / 薬 / atsuko_state のローカル DB (SQLite)。

    state.db (kyojuro_memory_persistence) とは別 DB として独立させる。
    health 専用の細粒度ログを保持し、必要に応じて memory_persistence へエクスポート。
    """

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_HEALTH_SCHEMA)

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "HealthStore":
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

    # -- symptom log -------------------------------------------------------

    def record_symptom(
        self,
        symptom: str,
        severity: int = 3,
        notes: str = "",
        pressure_hpa: Optional[float] = None,
        medication: Optional[str] = None,
        timestamp: Optional[str] = None,
    ) -> int:
        if symptom not in SYMPTOM_KEYS:
            raise ValueError(
                f"symptom は {SYMPTOM_KEYS} のいずれか、もしくは 'other': {symptom!r}"
            )
        if not (1 <= int(severity) <= 5):
            raise ValueError(f"severity は 1-5: {severity}")
        ts = timestamp if timestamp else _now_iso()
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO symptom_log
                    (timestamp, symptom, severity, notes, pressure_hpa, medication)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (ts, symptom, int(severity), notes, pressure_hpa, medication),
            )
            return int(cur.lastrowid)

    def list_symptoms(
        self,
        symptom: Optional[str] = None,
        since: Optional[str] = None,
        limit: int = 50,
    ) -> list[SymptomEntry]:
        clauses: list[str] = []
        params: list[Any] = []
        if symptom is not None:
            clauses.append("symptom = ?")
            params.append(symptom)
        if since is not None:
            clauses.append("timestamp >= ?")
            params.append(since)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = f"SELECT * FROM symptom_log {where} ORDER BY timestamp DESC LIMIT ?"
        params.append(int(limit))
        with self._cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        return [_row_to_symptom(r) for r in rows]

    # -- medication log ----------------------------------------------------

    def record_medication(
        self,
        medication: str,
        dose: str = "",
        notes: str = "",
        timestamp: Optional[str] = None,
    ) -> int:
        if not medication or not medication.strip():
            raise ValueError("medication は空であってはならない")
        ts = timestamp if timestamp else _now_iso()
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO medication_log
                    (timestamp, medication, dose, notes)
                VALUES (?, ?, ?, ?)
                """,
                (ts, medication, dose, notes),
            )
            return int(cur.lastrowid)

    def list_medications(
        self,
        medication: Optional[str] = None,
        since: Optional[str] = None,
        limit: int = 50,
    ) -> list[MedicationEntry]:
        clauses: list[str] = []
        params: list[Any] = []
        if medication is not None:
            clauses.append("medication = ?")
            params.append(medication)
        if since is not None:
            clauses.append("timestamp >= ?")
            params.append(since)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = f"SELECT * FROM medication_log {where} ORDER BY timestamp DESC LIMIT ?"
        params.append(int(limit))
        with self._cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        return [_row_to_medication(r) for r in rows]

    def medication_count_within(
        self,
        medication: str,
        hours: int = 24,
        now: Optional[datetime] = None,
    ) -> int:
        """指定時間内の服用回数を返す (ロキソニンの 6h 間隔チェック等)。"""
        now_dt = now if now is not None else datetime.now(tz=timezone.utc)
        since_dt = now_dt - timedelta(hours=int(hours))
        since_iso = since_dt.isoformat()
        with self._cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM medication_log WHERE medication = ? AND timestamp >= ?",
                (medication, since_iso),
            )
            return int(cur.fetchone()[0])

    # -- atsuko_state snapshot ---------------------------------------------

    def save_state_snapshot(self, state: AtsukoState, timestamp: Optional[str] = None) -> int:
        ts = timestamp if timestamp else _now_iso()
        with self._cursor() as cur:
            cur.execute(
                "INSERT INTO atsuko_state_snapshot (timestamp, state_json) VALUES (?, ?)",
                (ts, json.dumps(state.to_dict(), ensure_ascii=False)),
            )
            return int(cur.lastrowid)

    def latest_state(self) -> Optional[AtsukoState]:
        with self._cursor() as cur:
            cur.execute(
                "SELECT state_json FROM atsuko_state_snapshot ORDER BY timestamp DESC LIMIT 1"
            )
            row = cur.fetchone()
        if row is None:
            return None
        try:
            data = json.loads(row[0])
            return AtsukoState(
                jaw_pain=bool(data.get("jaw_pain", False)),
                left_hand_stiff=bool(data.get("left_hand_stiff", False)),
                low_pressure=bool(data.get("low_pressure", False)),
                shallow_sleep=bool(data.get("shallow_sleep", False)),
                headache=bool(data.get("headache", False)),
                dizziness=bool(data.get("dizziness", False)),
                sluggish=bool(data.get("sluggish", False)),
                notes=str(data.get("notes", "")),
            )
        except (ValueError, TypeError):
            return None


# ---------------------------------------------------------------------------
# pressure-symptom 相関 (簡易、LLM 不要)
# ---------------------------------------------------------------------------


def correlate_pressure_symptoms(
    symptoms: list[SymptomEntry],
    low_threshold: float = PRESSURE_LOW_THRESHOLD,
) -> dict[str, Any]:
    """症状と気圧の相関を簡易に計算する。

    Returns:
        {
            "total": 全症状数,
            "with_pressure": 気圧記録あり,
            "low_pressure_count": 低気圧時の症状数,
            "low_pressure_ratio": 低気圧時の割合 (0-1),
            "by_symptom": {symptom: {"low_pressure": N, "total": N}},
        }
    """
    total = len(symptoms)
    with_pressure = sum(1 for s in symptoms if s.pressure_hpa is not None)
    low_pressure_count = sum(
        1 for s in symptoms if s.pressure_hpa is not None and s.pressure_hpa < low_threshold
    )
    by_symptom: dict[str, dict[str, int]] = {}
    for s in symptoms:
        bucket = by_symptom.setdefault(s.symptom, {"low_pressure": 0, "total": 0})
        bucket["total"] += 1
        if s.pressure_hpa is not None and s.pressure_hpa < low_threshold:
            bucket["low_pressure"] += 1

    ratio = (low_pressure_count / with_pressure) if with_pressure > 0 else 0.0
    return {
        "total": total,
        "with_pressure": with_pressure,
        "low_pressure_count": low_pressure_count,
        "low_pressure_ratio": ratio,
        "by_symptom": by_symptom,
    }


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _row_to_symptom(row: sqlite3.Row) -> SymptomEntry:
    return SymptomEntry(
        id=int(row["id"]),
        timestamp_iso=str(row["timestamp"]),
        symptom=str(row["symptom"]),
        severity=int(row["severity"]),
        notes=str(row["notes"]),
        pressure_hpa=float(row["pressure_hpa"]) if row["pressure_hpa"] is not None else None,
        medication=row["medication"],
    )


def _row_to_medication(row: sqlite3.Row) -> MedicationEntry:
    return MedicationEntry(
        id=int(row["id"]),
        timestamp_iso=str(row["timestamp"]),
        medication=str(row["medication"]),
        dose=str(row["dose"]),
        notes=str(row["notes"]),
    )
