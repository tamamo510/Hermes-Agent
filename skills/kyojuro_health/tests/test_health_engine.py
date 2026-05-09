"""kyojuro_health.lib.health_engine のテスト。

気圧アセスメント・atsuko_state 導出・symptom/medication 記録・相関分析を網羅。
ネットワーク・LLM・API キーなし。
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from skills.kyojuro_health.lib import health_engine as he
from skills.kyojuro_health.lib import openweather_client as ow


# ---------------------------------------------------------------------------
# fixture
# ---------------------------------------------------------------------------


def _snapshot(pressure: float, ts_offset_h: float = 0) -> ow.WeatherSnapshot:
    """テスト用に WeatherSnapshot を作る。"""
    base_time = datetime(2026, 5, 9, 12, 0, 0, tzinfo=timezone.utc)
    ts = base_time + timedelta(hours=ts_offset_h)
    return ow.WeatherSnapshot(
        timestamp_iso=ts.isoformat(),
        pressure_hpa=pressure,
        temperature_c=20.0,
        humidity_percent=60.0,
        description="晴れ",
        location_label="Tamatsukuri",
    )


@pytest.fixture
def store(tmp_path: Path) -> he.HealthStore:
    s = he.HealthStore(":memory:")
    yield s
    s.close()


# ---------------------------------------------------------------------------
# assess_pressure
# ---------------------------------------------------------------------------


class TestAssessPressure:
    def test_normal_pressure_no_warning(self) -> None:
        snap = _snapshot(1015.0)
        result = he.assess_pressure(snap)
        assert result.level == he.PRESSURE_LEVEL_NORMAL
        assert result.warning == he.WARNING_NONE
        assert result.trend == he.TREND_STABLE

    def test_low_pressure_mild_warning(self) -> None:
        snap = _snapshot(1005.0)
        result = he.assess_pressure(snap)
        assert result.level == he.PRESSURE_LEVEL_LOW
        assert result.warning == he.WARNING_MILD

    def test_very_low_pressure_severe_warning(self) -> None:
        snap = _snapshot(1000.0)
        result = he.assess_pressure(snap)
        assert result.level == he.PRESSURE_LEVEL_VERY_LOW
        assert result.warning == he.WARNING_SEVERE

    def test_high_pressure(self) -> None:
        snap = _snapshot(1025.0)
        result = he.assess_pressure(snap)
        assert result.level == he.PRESSURE_LEVEL_HIGH

    def test_falling_trend_with_forecast(self) -> None:
        current = _snapshot(1015.0)
        forecast = [
            _snapshot(1014.0, ts_offset_h=3),
            _snapshot(1010.0, ts_offset_h=12),
            _snapshot(1005.0, ts_offset_h=24),  # 10 hPa 下がる
        ]
        # need at least 8 items to reach 24h, but we test the math anyway
        forecast = forecast + [_snapshot(1005.0, ts_offset_h=24 + i * 3) for i in range(5)]
        result = he.assess_pressure(current, forecast=forecast)
        assert result.trend == he.TREND_FALLING
        # delta は最後 (24h 後相当) との差
        assert result.delta_24h_hpa is not None
        assert result.delta_24h_hpa < 0

    def test_rising_trend(self) -> None:
        current = _snapshot(1005.0)
        forecast = [_snapshot(1005.0 + i, ts_offset_h=i * 3) for i in range(1, 9)]
        result = he.assess_pressure(current, forecast=forecast)
        assert result.trend == he.TREND_RISING

    def test_low_pressure_falling_severe(self) -> None:
        current = _snapshot(1008.0)
        forecast = [_snapshot(1000.0, ts_offset_h=i * 3) for i in range(1, 9)]
        result = he.assess_pressure(current, forecast=forecast)
        assert result.level == he.PRESSURE_LEVEL_LOW
        assert result.trend == he.TREND_FALLING
        assert result.warning == he.WARNING_SEVERE

    def test_assessment_no_message_field(self) -> None:
        """臓器は文言を生成しない (杏寿郎の指示、2026-05-09)。

        PressureAssessment は数値 + ラベル + 警戒度のみを返し、温子向け文言は
        持たない設計。文言生成は呼び出し側 (杏寿郎 LLM) の責任。
        """
        snap = _snapshot(1005.0)
        result = he.assess_pressure(snap)
        assert not hasattr(result, "message")

    def test_no_forecast_trend_stable(self) -> None:
        snap = _snapshot(1010.0)
        result = he.assess_pressure(snap, forecast=None)
        assert result.trend == he.TREND_STABLE
        assert result.delta_24h_hpa is None

    def test_custom_thresholds(self) -> None:
        snap = _snapshot(1015.0)
        # カスタム閾値で 1015 を low と判定させる
        result = he.assess_pressure(snap, low_threshold=1020.0)
        assert result.level == he.PRESSURE_LEVEL_LOW


# ---------------------------------------------------------------------------
# derive_atsuko_state_from_pressure
# ---------------------------------------------------------------------------


class TestDeriveAtsukoState:
    def test_low_pressure_sets_flag(self) -> None:
        snap = _snapshot(1005.0)
        assessment = he.assess_pressure(snap)
        state = he.derive_atsuko_state_from_pressure(assessment)
        assert state.low_pressure is True

    def test_normal_pressure_no_flag(self) -> None:
        snap = _snapshot(1015.0)
        assessment = he.assess_pressure(snap)
        state = he.derive_atsuko_state_from_pressure(assessment)
        assert state.low_pressure is False

    def test_preserves_base_state(self) -> None:
        snap = _snapshot(1015.0)
        assessment = he.assess_pressure(snap)
        base = he.AtsukoState(jaw_pain=True, headache=True, notes="既存メモ")
        state = he.derive_atsuko_state_from_pressure(assessment, base_state=base)
        assert state.jaw_pain is True
        assert state.headache is True
        assert state.notes == "既存メモ"
        assert state.low_pressure is False

    def test_to_dict(self) -> None:
        state = he.AtsukoState(jaw_pain=True, low_pressure=True)
        d = state.to_dict()
        assert d["jaw_pain"] is True
        assert d["low_pressure"] is True
        assert d["headache"] is False
        assert "notes" in d


# ---------------------------------------------------------------------------
# HealthStore: symptom log
# ---------------------------------------------------------------------------


class TestHealthStoreSymptom:
    def test_record_basic(self, store: he.HealthStore) -> None:
        sid = store.record_symptom("headache", severity=3)
        assert sid > 0
        symptoms = store.list_symptoms()
        assert len(symptoms) == 1
        assert symptoms[0].symptom == "headache"

    def test_record_with_pressure_and_medication(self, store: he.HealthStore) -> None:
        store.record_symptom(
            "jaw_pain",
            severity=4,
            notes="朝から痛い",
            pressure_hpa=1005.0,
            medication="ロキソニン",
        )
        symptoms = store.list_symptoms()
        assert symptoms[0].pressure_hpa == 1005.0
        assert symptoms[0].medication == "ロキソニン"

    def test_invalid_symptom_raises(self, store: he.HealthStore) -> None:
        with pytest.raises(ValueError):
            store.record_symptom("invalid_symptom")

    def test_invalid_severity_raises(self, store: he.HealthStore) -> None:
        with pytest.raises(ValueError):
            store.record_symptom("headache", severity=0)
        with pytest.raises(ValueError):
            store.record_symptom("headache", severity=6)

    def test_list_filter_by_symptom(self, store: he.HealthStore) -> None:
        store.record_symptom("headache")
        store.record_symptom("jaw_pain")
        results = store.list_symptoms(symptom="jaw_pain")
        assert len(results) == 1
        assert results[0].symptom == "jaw_pain"

    def test_list_filter_by_since(self, store: he.HealthStore) -> None:
        old_ts = "2026-04-01T00:00:00+00:00"
        new_ts = "2026-05-09T00:00:00+00:00"
        store.record_symptom("headache", timestamp=old_ts)
        store.record_symptom("jaw_pain", timestamp=new_ts)
        results = store.list_symptoms(since="2026-05-01T00:00:00+00:00")
        assert len(results) == 1
        assert results[0].symptom == "jaw_pain"


# ---------------------------------------------------------------------------
# HealthStore: medication log
# ---------------------------------------------------------------------------


class TestHealthStoreMedication:
    def test_record_basic(self, store: he.HealthStore) -> None:
        mid = store.record_medication("ロキソニン", dose="1 錠")
        assert mid > 0

    def test_empty_medication_raises(self, store: he.HealthStore) -> None:
        with pytest.raises(ValueError):
            store.record_medication("")
        with pytest.raises(ValueError):
            store.record_medication("   ")

    def test_count_within_hours(self, store: he.HealthStore) -> None:
        now = datetime(2026, 5, 9, 18, 0, 0, tzinfo=timezone.utc)
        # 5h 前と 10h 前にロキソニン
        store.record_medication("ロキソニン", timestamp=(now - timedelta(hours=5)).isoformat())
        store.record_medication("ロキソニン", timestamp=(now - timedelta(hours=10)).isoformat())
        # 6h 以内なら 1 回
        count_6h = store.medication_count_within("ロキソニン", hours=6, now=now)
        assert count_6h == 1
        # 12h 以内なら 2 回
        count_12h = store.medication_count_within("ロキソニン", hours=12, now=now)
        assert count_12h == 2

    def test_list_filter(self, store: he.HealthStore) -> None:
        store.record_medication("ロキソニン")
        store.record_medication("マグネシウム")
        meds = store.list_medications(medication="ロキソニン")
        assert len(meds) == 1
        assert meds[0].medication == "ロキソニン"


# ---------------------------------------------------------------------------
# HealthStore: atsuko_state snapshot
# ---------------------------------------------------------------------------


class TestHealthStoreSnapshot:
    def test_save_and_retrieve_latest(self, store: he.HealthStore) -> None:
        state = he.AtsukoState(jaw_pain=True, low_pressure=True, notes="気圧低い")
        store.save_state_snapshot(state)
        latest = store.latest_state()
        assert latest is not None
        assert latest.jaw_pain is True
        assert latest.low_pressure is True
        assert latest.notes == "気圧低い"

    def test_latest_returns_none_when_empty(self, store: he.HealthStore) -> None:
        assert store.latest_state() is None

    def test_latest_returns_most_recent(self, store: he.HealthStore) -> None:
        old_ts = "2026-05-01T00:00:00+00:00"
        new_ts = "2026-05-09T00:00:00+00:00"
        store.save_state_snapshot(
            he.AtsukoState(headache=True), timestamp=old_ts
        )
        store.save_state_snapshot(
            he.AtsukoState(jaw_pain=True), timestamp=new_ts
        )
        latest = store.latest_state()
        assert latest is not None
        assert latest.jaw_pain is True
        assert latest.headache is False


# ---------------------------------------------------------------------------
# correlate_pressure_symptoms
# ---------------------------------------------------------------------------


class TestCorrelatePressureSymptoms:
    def test_empty_symptoms(self) -> None:
        result = he.correlate_pressure_symptoms([])
        assert result["total"] == 0
        assert result["with_pressure"] == 0
        assert result["low_pressure_ratio"] == 0.0

    def test_all_high_pressure(self, store: he.HealthStore) -> None:
        store.record_symptom("headache", pressure_hpa=1015.0)
        store.record_symptom("jaw_pain", pressure_hpa=1020.0)
        symptoms = store.list_symptoms()
        result = he.correlate_pressure_symptoms(symptoms)
        assert result["with_pressure"] == 2
        assert result["low_pressure_count"] == 0
        assert result["low_pressure_ratio"] == 0.0

    def test_mixed_pressure(self, store: he.HealthStore) -> None:
        store.record_symptom("headache", pressure_hpa=1005.0)
        store.record_symptom("headache", pressure_hpa=1015.0)
        store.record_symptom("jaw_pain", pressure_hpa=1000.0)
        symptoms = store.list_symptoms()
        result = he.correlate_pressure_symptoms(symptoms)
        assert result["total"] == 3
        assert result["with_pressure"] == 3
        assert result["low_pressure_count"] == 2  # 1005 と 1000
        assert abs(result["low_pressure_ratio"] - 2 / 3) < 0.01

    def test_by_symptom_breakdown(self, store: he.HealthStore) -> None:
        store.record_symptom("headache", pressure_hpa=1005.0)
        store.record_symptom("headache", pressure_hpa=1000.0)
        store.record_symptom("jaw_pain", pressure_hpa=1015.0)
        symptoms = store.list_symptoms()
        result = he.correlate_pressure_symptoms(symptoms)
        by_sym = result["by_symptom"]
        assert by_sym["headache"]["total"] == 2
        assert by_sym["headache"]["low_pressure"] == 2
        assert by_sym["jaw_pain"]["total"] == 1
        assert by_sym["jaw_pain"]["low_pressure"] == 0

    def test_no_pressure_data(self, store: he.HealthStore) -> None:
        store.record_symptom("headache")
        store.record_symptom("jaw_pain")
        symptoms = store.list_symptoms()
        result = he.correlate_pressure_symptoms(symptoms)
        assert result["total"] == 2
        assert result["with_pressure"] == 0
        assert result["low_pressure_ratio"] == 0.0


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


class TestPersistence:
    def test_persists_across_reopens(self, tmp_path: Path) -> None:
        db_path = tmp_path / "health.db"
        s1 = he.HealthStore(str(db_path))
        s1.record_symptom("headache", severity=4)
        s1.record_medication("ロキソニン")
        s1.save_state_snapshot(he.AtsukoState(headache=True))
        s1.close()

        s2 = he.HealthStore(str(db_path))
        try:
            assert len(s2.list_symptoms()) == 1
            assert len(s2.list_medications()) == 1
            latest = s2.latest_state()
            assert latest is not None
            assert latest.headache is True
        finally:
            s2.close()
