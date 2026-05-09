"""kyojuro_health.lib.openweather_client のテスト。

実 API は呼ばない。HTTP クライアントを mock し、CLAUDE.md ルール 17 を遵守する。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import pytest

from skills.kyojuro_health.lib import env_loader as el
from skills.kyojuro_health.lib import openweather_client as ow


# ---------------------------------------------------------------------------
# モック HTTP クライアント
# ---------------------------------------------------------------------------


@dataclass
class MockResponse:
    """`requests.Response` 互換の最小モック。"""

    status_code: int = 200
    body: Any = None
    text_body: str = ""
    raise_on_json: bool = False

    def json(self) -> Any:
        if self.raise_on_json:
            raise ValueError("invalid json")
        return self.body

    @property
    def text(self) -> str:
        return self.text_body


class MockHttpClient:
    """`requests` 互換のモック HTTP クライアント。

    予めレスポンスを set_response() で登録し、get() の呼び出し記録を残す。
    """

    def __init__(self) -> None:
        self.responses: dict[str, MockResponse] = {}
        self.calls: list[tuple[str, dict[str, Any], int]] = []
        self.raise_exception: Optional[Exception] = None

    def set_response(self, url: str, response: MockResponse) -> None:
        self.responses[url] = response

    def get(
        self,
        url: str,
        params: Optional[dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> MockResponse:
        self.calls.append((url, params or {}, int(timeout or 0)))
        if self.raise_exception is not None:
            raise self.raise_exception
        if url not in self.responses:
            raise AssertionError(f"未設定の URL がリクエストされた: {url}")
        return self.responses[url]


# ---------------------------------------------------------------------------
# fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def env() -> dict[str, str]:
    return {
        el.ENV_OPENWEATHER_API_KEY: "test-key-abcdef",
        el.ENV_OPENWEATHER_LAT: "34.6724",
        el.ENV_OPENWEATHER_LON: "135.5325",
    }


@pytest.fixture
def mock_http() -> MockHttpClient:
    return MockHttpClient()


# ---------------------------------------------------------------------------
# WeatherSnapshot.from_openweather_current
# ---------------------------------------------------------------------------


class TestWeatherSnapshotFromCurrent:
    def test_basic_parse(self) -> None:
        payload = {
            "dt": 1730000000,
            "main": {"pressure": 1013.5, "temp": 22.4, "humidity": 65},
            "weather": [{"description": "晴れ"}],
            "name": "Tamatsukuri",
        }
        snap = ow.WeatherSnapshot.from_openweather_current(payload)
        assert snap.pressure_hpa == 1013.5
        assert snap.temperature_c == 22.4
        assert snap.humidity_percent == 65
        assert snap.description == "晴れ"
        assert snap.location_label == "Tamatsukuri"

    def test_missing_pressure_raises(self) -> None:
        payload = {"main": {"temp": 22.0}, "weather": [{}]}
        with pytest.raises(ow.OpenWeatherResponseError):
            ow.WeatherSnapshot.from_openweather_current(payload)

    def test_missing_main_raises(self) -> None:
        payload = {"weather": [{}]}
        with pytest.raises(ow.OpenWeatherResponseError):
            ow.WeatherSnapshot.from_openweather_current(payload)

    def test_no_weather_array_handled(self) -> None:
        payload = {
            "dt": 1730000000,
            "main": {"pressure": 1013, "temp": 20, "humidity": 50},
            "name": "test",
        }
        snap = ow.WeatherSnapshot.from_openweather_current(payload)
        assert snap.description == ""

    def test_iso_timestamp_format(self) -> None:
        payload = {
            "dt": 1730000000,
            "main": {"pressure": 1013, "temp": 20, "humidity": 50},
            "weather": [{"description": "曇り"}],
            "name": "test",
        }
        snap = ow.WeatherSnapshot.from_openweather_current(payload)
        # ISO 8601 形式
        assert "T" in snap.timestamp_iso


# ---------------------------------------------------------------------------
# WeatherSnapshot.from_openweather_forecast_item
# ---------------------------------------------------------------------------


class TestWeatherSnapshotFromForecast:
    def test_basic_parse(self) -> None:
        item = {
            "dt": 1730003600,
            "main": {"pressure": 1010, "temp": 20, "humidity": 70},
            "weather": [{"description": "雨"}],
        }
        snap = ow.WeatherSnapshot.from_openweather_forecast_item(item, location_label="Osaka")
        assert snap.pressure_hpa == 1010
        assert snap.temperature_c == 20
        assert snap.location_label == "Osaka"

    def test_invalid_raises(self) -> None:
        with pytest.raises(ow.OpenWeatherResponseError):
            ow.WeatherSnapshot.from_openweather_forecast_item({})


# ---------------------------------------------------------------------------
# OpenWeatherClient 初期化
# ---------------------------------------------------------------------------


class TestOpenWeatherClientInit:
    def test_uses_env_for_key_and_coords(
        self, env: dict[str, str], mock_http: MockHttpClient
    ) -> None:
        client = ow.OpenWeatherClient(http_client=mock_http, env=env)
        assert client.api_key == "test-key-abcdef"
        assert client.lat == 34.6724
        assert client.lon == 135.5325

    def test_explicit_args_override_env(
        self, env: dict[str, str], mock_http: MockHttpClient
    ) -> None:
        client = ow.OpenWeatherClient(
            api_key="explicit-key",
            lat=40.0,
            lon=140.0,
            http_client=mock_http,
            env=env,
        )
        assert client.api_key == "explicit-key"
        assert client.lat == 40.0
        assert client.lon == 140.0

    def test_missing_api_key_raises(self, mock_http: MockHttpClient) -> None:
        with pytest.raises(el.MissingEnvVarError):
            ow.OpenWeatherClient(http_client=mock_http, env={})


# ---------------------------------------------------------------------------
# get_current_weather
# ---------------------------------------------------------------------------


class TestGetCurrentWeather:
    def test_successful_call(
        self, env: dict[str, str], mock_http: MockHttpClient
    ) -> None:
        mock_http.set_response(
            ow.OPENWEATHER_BASE_URL,
            MockResponse(
                status_code=200,
                body={
                    "dt": 1730000000,
                    "main": {"pressure": 1013, "temp": 20, "humidity": 60},
                    "weather": [{"description": "晴れ"}],
                    "name": "Tamatsukuri",
                },
            ),
        )
        client = ow.OpenWeatherClient(http_client=mock_http, env=env)
        snap = client.get_current_weather()
        assert snap.pressure_hpa == 1013
        assert snap.location_label == "Tamatsukuri"
        # API キーがリクエストに含まれている
        url, params, _ = mock_http.calls[0]
        assert params["appid"] == "test-key-abcdef"
        assert params["lat"] == 34.6724
        assert params["lon"] == 135.5325
        assert params["units"] == "metric"
        assert params["lang"] == "ja"

    def test_401_raises_auth_error(
        self, env: dict[str, str], mock_http: MockHttpClient
    ) -> None:
        mock_http.set_response(
            ow.OPENWEATHER_BASE_URL,
            MockResponse(status_code=401, text_body="Invalid key"),
        )
        client = ow.OpenWeatherClient(http_client=mock_http, env=env)
        with pytest.raises(ow.OpenWeatherAuthError):
            client.get_current_weather()

    def test_500_raises_generic_error(
        self, env: dict[str, str], mock_http: MockHttpClient
    ) -> None:
        mock_http.set_response(
            ow.OPENWEATHER_BASE_URL,
            MockResponse(status_code=500, text_body="server error"),
        )
        client = ow.OpenWeatherClient(http_client=mock_http, env=env)
        with pytest.raises(ow.OpenWeatherError):
            client.get_current_weather()

    def test_network_error(
        self, env: dict[str, str], mock_http: MockHttpClient
    ) -> None:
        mock_http.raise_exception = ConnectionError("network down")
        client = ow.OpenWeatherClient(http_client=mock_http, env=env)
        with pytest.raises(ow.OpenWeatherNetworkError):
            client.get_current_weather()

    def test_invalid_json_raises(
        self, env: dict[str, str], mock_http: MockHttpClient
    ) -> None:
        mock_http.set_response(
            ow.OPENWEATHER_BASE_URL,
            MockResponse(status_code=200, raise_on_json=True),
        )
        client = ow.OpenWeatherClient(http_client=mock_http, env=env)
        with pytest.raises(ow.OpenWeatherResponseError):
            client.get_current_weather()

    def test_non_dict_body_raises(
        self, env: dict[str, str], mock_http: MockHttpClient
    ) -> None:
        mock_http.set_response(
            ow.OPENWEATHER_BASE_URL,
            MockResponse(status_code=200, body=["not", "a", "dict"]),
        )
        client = ow.OpenWeatherClient(http_client=mock_http, env=env)
        with pytest.raises(ow.OpenWeatherResponseError):
            client.get_current_weather()


# ---------------------------------------------------------------------------
# get_forecast
# ---------------------------------------------------------------------------


class TestGetForecast:
    def test_basic_forecast(
        self, env: dict[str, str], mock_http: MockHttpClient
    ) -> None:
        mock_http.set_response(
            ow.OPENWEATHER_FORECAST_URL,
            MockResponse(
                status_code=200,
                body={
                    "list": [
                        {
                            "dt": 1730003600,
                            "main": {"pressure": 1010, "temp": 19, "humidity": 70},
                            "weather": [{"description": "雨"}],
                        },
                        {
                            "dt": 1730014400,
                            "main": {"pressure": 1008, "temp": 18, "humidity": 75},
                            "weather": [{"description": "雨"}],
                        },
                    ],
                    "city": {"name": "Osaka"},
                },
            ),
        )
        client = ow.OpenWeatherClient(http_client=mock_http, env=env)
        snaps = client.get_forecast(hours_ahead=6)
        assert len(snaps) == 2
        assert snaps[0].pressure_hpa == 1010
        assert snaps[1].pressure_hpa == 1008
        assert snaps[0].location_label == "Osaka"
        # cnt パラメータが計算されている
        _, params, _ = mock_http.calls[0]
        assert params.get("cnt") == 2  # 6h / 3h = 2

    def test_invalid_hours_ahead_raises(
        self, env: dict[str, str], mock_http: MockHttpClient
    ) -> None:
        client = ow.OpenWeatherClient(http_client=mock_http, env=env)
        with pytest.raises(ValueError):
            client.get_forecast(hours_ahead=0)
        with pytest.raises(ValueError):
            client.get_forecast(hours_ahead=-1)

    def test_missing_list_raises(
        self, env: dict[str, str], mock_http: MockHttpClient
    ) -> None:
        mock_http.set_response(
            ow.OPENWEATHER_FORECAST_URL,
            MockResponse(status_code=200, body={"city": {"name": "Osaka"}}),
        )
        client = ow.OpenWeatherClient(http_client=mock_http, env=env)
        with pytest.raises(ow.OpenWeatherResponseError):
            client.get_forecast(hours_ahead=6)

    def test_cnt_capped_at_40(
        self, env: dict[str, str], mock_http: MockHttpClient
    ) -> None:
        mock_http.set_response(
            ow.OPENWEATHER_FORECAST_URL,
            MockResponse(status_code=200, body={"list": [], "city": {"name": "test"}}),
        )
        client = ow.OpenWeatherClient(http_client=mock_http, env=env)
        # 200 時間先 = 67 件相当だが 40 で capped
        client.get_forecast(hours_ahead=200)
        _, params, _ = mock_http.calls[0]
        assert params.get("cnt") == 40
