"""kyojuro_health.handler のテスト。

実 OpenWeatherMap API は呼ばない。HTTP クライアント注入で完結。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from skills.kyojuro_health import handler as h
from skills.kyojuro_health.lib import env_loader as el
from skills.kyojuro_health.lib import health_engine as he
from skills.kyojuro_health.lib import openweather_client as ow
from skills.kyojuro_health.tests.test_openweather_client import MockHttpClient, MockResponse


# ---------------------------------------------------------------------------
# fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def store() -> he.HealthStore:
    s = he.HealthStore(":memory:")
    yield s
    s.close()


@pytest.fixture
def env() -> dict[str, str]:
    return {
        el.ENV_OPENWEATHER_API_KEY: "test-key",
        el.ENV_OPENWEATHER_LAT: "34.6724",
        el.ENV_OPENWEATHER_LON: "135.5325",
    }


def _setup_client(
    pressure_now: float = 1015.0,
    pressure_24h: float | None = None,
    env: dict[str, str] | None = None,
) -> tuple[ow.OpenWeatherClient, MockHttpClient]:
    mock_http = MockHttpClient()
    mock_http.set_response(
        ow.OPENWEATHER_BASE_URL,
        MockResponse(
            status_code=200,
            body={
                "dt": 1730000000,
                "main": {"pressure": pressure_now, "temp": 20, "humidity": 60},
                "weather": [{"description": "晴れ"}],
                "name": "Tamatsukuri",
            },
        ),
    )
    if pressure_24h is not None:
        forecast_items = [
            {
                "dt": 1730000000 + i * 10800,
                "main": {"pressure": pressure_24h, "temp": 20, "humidity": 60},
                "weather": [{"description": "曇り"}],
            }
            for i in range(8)
        ]
        mock_http.set_response(
            ow.OPENWEATHER_FORECAST_URL,
            MockResponse(
                status_code=200,
                body={"list": forecast_items, "city": {"name": "Osaka"}},
            ),
        )
    else:
        mock_http.set_response(
            ow.OPENWEATHER_FORECAST_URL,
            MockResponse(
                status_code=200,
                body={"list": [], "city": {"name": "Osaka"}},
            ),
        )
    client = ow.OpenWeatherClient(http_client=mock_http, env=env or {
        el.ENV_OPENWEATHER_API_KEY: "test-key",
    })
    return client, mock_http


# ---------------------------------------------------------------------------
# detect_symptom / detect_medication
# ---------------------------------------------------------------------------


class TestDetectSymptom:
    def test_headache(self) -> None:
        assert h.detect_symptom("頭痛い") == "headache"

    def test_jaw_pain(self) -> None:
        assert h.detect_symptom("顎が痛い") == "jaw_pain"

    def test_left_hand_stiff(self) -> None:
        assert h.detect_symptom("左手が硬くなった") == "left_hand_stiff"

    def test_shallow_sleep(self) -> None:
        assert h.detect_symptom("眠り浅くて")  == "shallow_sleep"

    def test_dizziness(self) -> None:
        assert h.detect_symptom("ふらつきがある") == "dizziness"

    def test_sluggish(self) -> None:
        assert h.detect_symptom("だる重い") == "sluggish"

    def test_unknown_returns_none(self) -> None:
        assert h.detect_symptom("こんにちは") is None


class TestDetectMedication:
    def test_loxonin(self) -> None:
        assert h.detect_medication("ロキソニン飲んだ") == "ロキソニン"

    def test_magnesium(self) -> None:
        assert h.detect_medication("マグネシウム摂った") == "マグネシウム"

    def test_dmae(self) -> None:
        assert h.detect_medication("DMAE 服用") == "DMAE"

    def test_pill(self) -> None:
        assert h.detect_medication("ピル飲んだ") == "ピル"

    def test_unknown_returns_none(self) -> None:
        assert h.detect_medication("お茶飲んだ") is None


# ---------------------------------------------------------------------------
# HealthHandler 初期化
# ---------------------------------------------------------------------------


class TestHandlerInit:
    def test_lazy_client_initialization(self, store: he.HealthStore) -> None:
        # client=None で起動できる (環境変数なくてもロード可能)
        handler = h.HealthHandler(store, client=None)
        assert handler._client is None

    def test_explicit_client(self, store: he.HealthStore) -> None:
        client, _ = _setup_client()
        handler = h.HealthHandler(store, client=client)
        assert handler._client is client


# ---------------------------------------------------------------------------
# on_user_message
# ---------------------------------------------------------------------------


class TestOnUserMessage:
    def test_records_symptom(self, store: he.HealthStore) -> None:
        handler = h.HealthHandler(store)
        result = handler.on_user_message("頭痛い")
        assert result.symptom_recorded is True
        assert result.detected_symptom == "headache"
        assert len(store.list_symptoms()) == 1

    def test_records_medication(self, store: he.HealthStore) -> None:
        handler = h.HealthHandler(store)
        result = handler.on_user_message("ロキソニン飲んだ")
        assert result.medication_recorded is True
        assert result.detected_medication == "ロキソニン"
        assert len(store.list_medications()) == 1

    def test_records_both(self, store: he.HealthStore) -> None:
        handler = h.HealthHandler(store)
        result = handler.on_user_message("頭痛くてロキソニン飲んだ")
        assert result.symptom_recorded is True
        assert result.medication_recorded is True

    def test_no_pattern_no_record(self, store: he.HealthStore) -> None:
        handler = h.HealthHandler(store)
        result = handler.on_user_message("こんにちは")
        assert result.symptom_recorded is False
        assert result.medication_recorded is False
        assert store.list_symptoms() == []

    def test_with_pressure_hpa(self, store: he.HealthStore) -> None:
        handler = h.HealthHandler(store)
        handler.on_user_message("頭痛い", pressure_hpa=1005.0)
        symptoms = store.list_symptoms()
        assert symptoms[0].pressure_hpa == 1005.0

    def test_empty_message_no_record(self, store: he.HealthStore) -> None:
        handler = h.HealthHandler(store)
        result = handler.on_user_message("")
        assert result.symptom_recorded is False


# ---------------------------------------------------------------------------
# on_conversation_start / daily_briefing
# ---------------------------------------------------------------------------


class TestOnConversationStart:
    def test_skip_network_returns_latest_state(
        self, store: he.HealthStore
    ) -> None:
        store.save_state_snapshot(
            he.AtsukoState(jaw_pain=True, low_pressure=True)
        )
        handler = h.HealthHandler(store)
        briefing = handler.on_conversation_start(skip_network=True)
        assert briefing.weather is None
        assert briefing.assessment is None
        assert briefing.atsuko_state.jaw_pain is True
        assert briefing.atsuko_state.low_pressure is True

    def test_skip_network_with_no_state(self, store: he.HealthStore) -> None:
        handler = h.HealthHandler(store)
        briefing = handler.on_conversation_start(skip_network=True)
        assert briefing.atsuko_state == he.AtsukoState()

    def test_with_network_low_pressure(self, store: he.HealthStore) -> None:
        client, _ = _setup_client(pressure_now=1005.0)
        handler = h.HealthHandler(store, client=client)
        briefing = handler.on_conversation_start()
        assert briefing.weather is not None
        assert briefing.weather.pressure_hpa == 1005.0
        assert briefing.assessment is not None
        assert briefing.assessment.level == he.PRESSURE_LEVEL_LOW
        assert briefing.atsuko_state.low_pressure is True

    def test_missing_api_key_returns_error(self, store: he.HealthStore) -> None:
        handler = h.HealthHandler(store)
        # 環境変数を空にする
        from unittest.mock import patch

        with patch.dict("os.environ", {}, clear=True):
            briefing = handler.on_conversation_start()
        assert briefing.error_message is not None
        assert ".env" in briefing.error_message

    def test_network_error_returns_error_message(
        self, store: he.HealthStore
    ) -> None:
        client, mock_http = _setup_client()
        mock_http.raise_exception = ConnectionError("network down")
        handler = h.HealthHandler(store, client=client)
        briefing = handler.on_conversation_start()
        assert briefing.error_message is not None


# ---------------------------------------------------------------------------
# on_schedule_tick
# ---------------------------------------------------------------------------


class TestOnScheduleTick:
    def test_saves_snapshot(self, store: he.HealthStore) -> None:
        client, _ = _setup_client(pressure_now=1005.0)
        handler = h.HealthHandler(store, client=client)
        handler.on_schedule_tick()
        latest = store.latest_state()
        assert latest is not None
        assert latest.low_pressure is True

    def test_skip_network_no_save(self, store: he.HealthStore) -> None:
        handler = h.HealthHandler(store)
        handler.on_schedule_tick(skip_network=True)
        # スナップショット保存されない
        assert store.latest_state() is None

    def test_failure_no_save(self, store: he.HealthStore) -> None:
        # ネットワークエラー時は state を保存しない
        client, mock_http = _setup_client()
        mock_http.raise_exception = ConnectionError("fail")
        handler = h.HealthHandler(store, client=client)
        handler.on_schedule_tick()
        assert store.latest_state() is None


# ---------------------------------------------------------------------------
# get_atsuko_state / update_atsuko_state
# ---------------------------------------------------------------------------


class TestAtsukoStateAccess:
    def test_get_returns_empty_when_no_data(self, store: he.HealthStore) -> None:
        handler = h.HealthHandler(store)
        state = handler.get_atsuko_state()
        assert state == he.AtsukoState()

    def test_get_returns_latest(self, store: he.HealthStore) -> None:
        store.save_state_snapshot(he.AtsukoState(jaw_pain=True, headache=True))
        handler = h.HealthHandler(store)
        state = handler.get_atsuko_state()
        assert state.jaw_pain is True
        assert state.headache is True

    def test_update_partial(self, store: he.HealthStore) -> None:
        store.save_state_snapshot(he.AtsukoState(jaw_pain=True))
        handler = h.HealthHandler(store)
        new_state = handler.update_atsuko_state(headache=True)
        # 既存 jaw_pain は保持、headache が新規追加
        assert new_state.jaw_pain is True
        assert new_state.headache is True

    def test_update_persists(self, store: he.HealthStore) -> None:
        handler = h.HealthHandler(store)
        handler.update_atsuko_state(jaw_pain=True, low_pressure=True, notes="気圧低い")
        latest = store.latest_state()
        assert latest is not None
        assert latest.jaw_pain is True
        assert latest.notes == "気圧低い"


# ---------------------------------------------------------------------------
# 手動記録
# ---------------------------------------------------------------------------


class TestManualRecord:
    def test_record_symptom_manual(self, store: he.HealthStore) -> None:
        handler = h.HealthHandler(store)
        sid = handler.record_symptom_manual(
            symptom="headache",
            severity=4,
            notes="朝からずっと",
            pressure_hpa=1005.0,
            medication="ロキソニン",
        )
        assert sid > 0
        symptoms = store.list_symptoms()
        assert symptoms[0].severity == 4
        assert symptoms[0].medication == "ロキソニン"

    def test_record_medication_manual(self, store: he.HealthStore) -> None:
        handler = h.HealthHandler(store)
        mid = handler.record_medication_manual(
            medication="ロキソニン", dose="1 錠", notes="頭痛のため"
        )
        assert mid > 0


# ---------------------------------------------------------------------------
# medication warning
# ---------------------------------------------------------------------------


class TestMedicationWarning:
    def test_loxonin_three_in_24h_warns(self, store: he.HealthStore) -> None:
        client, _ = _setup_client(pressure_now=1015.0)
        handler = h.HealthHandler(store, client=client)
        # 3 回ロキソニン記録 (現在時刻から逆算)
        now = datetime.now(tz=timezone.utc)
        for hours_ago in [1, 7, 13]:
            store.record_medication(
                "ロキソニン",
                timestamp=(now - timedelta(hours=hours_ago)).isoformat(),
            )
        briefing = handler.on_conversation_start()
        assert any("ロキソニン" in w for w in briefing.medication_warnings)

    def test_loxonin_two_no_warn(self, store: he.HealthStore) -> None:
        client, _ = _setup_client(pressure_now=1015.0)
        handler = h.HealthHandler(store, client=client)
        now = datetime.now(tz=timezone.utc)
        for hours_ago in [1, 7]:
            store.record_medication(
                "ロキソニン",
                timestamp=(now - timedelta(hours=hours_ago)).isoformat(),
            )
        briefing = handler.on_conversation_start()
        assert briefing.medication_warnings == []


# ---------------------------------------------------------------------------
# briefing.message
# ---------------------------------------------------------------------------


class TestBriefingMessage:
    def test_message_with_assessment(self, store: he.HealthStore) -> None:
        client, _ = _setup_client(pressure_now=1005.0)
        handler = h.HealthHandler(store, client=client)
        briefing = handler.on_conversation_start()
        assert "1005" in briefing.message
        assert "hPa" in briefing.message

    def test_message_with_error(self, store: he.HealthStore) -> None:
        from unittest.mock import patch

        handler = h.HealthHandler(store)
        with patch.dict("os.environ", {}, clear=True):
            briefing = handler.on_conversation_start()
        assert ".env" in briefing.message

    def test_message_with_warnings(self, store: he.HealthStore) -> None:
        client, _ = _setup_client(pressure_now=1015.0)
        handler = h.HealthHandler(store, client=client)
        now = datetime.now(tz=timezone.utc)
        for hours_ago in [1, 7, 13]:
            store.record_medication(
                "ロキソニン",
                timestamp=(now - timedelta(hours=hours_ago)).isoformat(),
            )
        briefing = handler.on_conversation_start()
        assert "ロキソニン" in briefing.message
