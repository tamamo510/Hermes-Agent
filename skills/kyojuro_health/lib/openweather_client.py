"""kyojuro_health.lib.openweather_client — OpenWeatherMap API クライアント。

発注書スキル 3-5 (気圧・体調連動) の前提となる気象データ取得。

設計原則:
- API キーは環境変数経由 (CLAUDE.md ルール 17)
- HTTP クライアントは `requests` を使用 (requirements.txt 方針)
- 失敗時はクリアな例外を上げる (温子が原因を理解できる形で)
- テストはモック化し、実 API は呼ばない
- WebARENA Indigo の自宅 LAN から呼ぶ前提
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional, Protocol

from .env_loader import get_openweather_api_key, get_openweather_coordinates


OPENWEATHER_BASE_URL = "https://api.openweathermap.org/data/2.5/weather"
OPENWEATHER_FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"

DEFAULT_TIMEOUT_SECONDS = 10
DEFAULT_UNITS = "metric"  # 摂氏 / hPa
DEFAULT_LANG = "ja"  # 日本語


# ---------------------------------------------------------------------------
# 例外
# ---------------------------------------------------------------------------


class OpenWeatherError(RuntimeError):
    """OpenWeatherMap API 呼び出しの汎用例外。"""


class OpenWeatherNetworkError(OpenWeatherError):
    """ネットワーク (タイムアウト・接続失敗等)。"""


class OpenWeatherAuthError(OpenWeatherError):
    """認証 (キー無効、401)。"""


class OpenWeatherResponseError(OpenWeatherError):
    """レスポンス内容が不正 (期待するフィールド欠如等)。"""


# ---------------------------------------------------------------------------
# データクラス
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WeatherSnapshot:
    """ある時刻の気象スナップショット。"""

    timestamp_iso: str  # ISO 8601 (UTC)
    pressure_hpa: float  # 気圧 (hPa)
    temperature_c: float  # 気温 (摂氏)
    humidity_percent: float  # 湿度 (%)
    description: str  # OpenWeather の天気説明 (日本語)
    location_label: str  # 場所のラベル (例: "Tamatsukuri, Osaka, JP")
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_openweather_current(cls, payload: dict[str, Any]) -> "WeatherSnapshot":
        """OpenWeatherMap /weather (current) のレスポンスから作成する。"""
        try:
            main = payload["main"]
            weather = payload.get("weather", [{}])[0]
            dt = payload.get("dt", 0)
            ts = datetime.fromtimestamp(int(dt), tz=timezone.utc).isoformat()
            return cls(
                timestamp_iso=ts,
                pressure_hpa=float(main["pressure"]),
                temperature_c=float(main["temp"]),
                humidity_percent=float(main.get("humidity", 0)),
                description=str(weather.get("description", "")),
                location_label=str(payload.get("name", "")),
                raw=dict(payload),
            )
        except (KeyError, TypeError, ValueError) as e:
            raise OpenWeatherResponseError(
                f"OpenWeather current レスポンスが不正: {e}"
            ) from e

    @classmethod
    def from_openweather_forecast_item(
        cls, item: dict[str, Any], location_label: str = ""
    ) -> "WeatherSnapshot":
        """OpenWeatherMap /forecast の 1 item から作成する。"""
        try:
            main = item["main"]
            weather = item.get("weather", [{}])[0]
            dt = item.get("dt", 0)
            ts = datetime.fromtimestamp(int(dt), tz=timezone.utc).isoformat()
            return cls(
                timestamp_iso=ts,
                pressure_hpa=float(main["pressure"]),
                temperature_c=float(main["temp"]),
                humidity_percent=float(main.get("humidity", 0)),
                description=str(weather.get("description", "")),
                location_label=location_label,
                raw=dict(item),
            )
        except (KeyError, TypeError, ValueError) as e:
            raise OpenWeatherResponseError(
                f"OpenWeather forecast item が不正: {e}"
            ) from e


# ---------------------------------------------------------------------------
# HTTP クライアント抽象 (テスト可能性のため)
# ---------------------------------------------------------------------------


class HttpClient(Protocol):
    """`requests` ライブラリと互換のミニマル HTTP クライアント Protocol。"""

    def get(
        self,
        url: str,
        params: Optional[dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> "HttpResponse": ...


class HttpResponse(Protocol):
    """`requests.Response` と互換のミニマル Protocol。"""

    @property
    def status_code(self) -> int: ...

    def json(self) -> Any: ...

    @property
    def text(self) -> str: ...


def _default_http_client() -> HttpClient:
    """`requests` を遅延 import して返す (テストはこの関数を使わない)。"""
    import requests  # type: ignore

    return requests  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# OpenWeatherClient
# ---------------------------------------------------------------------------


class OpenWeatherClient:
    """OpenWeatherMap API のラッパー。

    Args:
        api_key: API キー (None なら環境変数から読む)
        lat: 緯度 (None なら環境変数から)
        lon: 経度 (None なら環境変数から)
        http_client: テスト用の HTTP クライアント注入
        env: テスト用の環境変数注入
        timeout: HTTP タイムアウト秒
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        http_client: Optional[HttpClient] = None,
        env: Optional[dict[str, str]] = None,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        # 環境変数から読み取り (api_key 直渡しを優先するが、CLAUDE.md ルール 17 を遵守し
        # 通常運用では環境変数経由のみ)
        self.api_key = api_key if api_key is not None else get_openweather_api_key(env)
        if lat is None or lon is None:
            env_lat, env_lon = get_openweather_coordinates(env)
            self.lat = lat if lat is not None else env_lat
            self.lon = lon if lon is not None else env_lon
        else:
            self.lat = lat
            self.lon = lon
        self.http_client = http_client if http_client is not None else _default_http_client()
        self.timeout = int(timeout)

    # -- public API --------------------------------------------------------

    def get_current_weather(self) -> WeatherSnapshot:
        """現在の気象を取得する。"""
        params = self._common_params()
        payload = self._call(OPENWEATHER_BASE_URL, params)
        return WeatherSnapshot.from_openweather_current(payload)

    def get_forecast(self, hours_ahead: int = 24) -> list[WeatherSnapshot]:
        """指定時間先までの予報を取得する (OpenWeather は 3 時間刻み、5 日先まで)。"""
        if hours_ahead <= 0:
            raise ValueError(f"hours_ahead は正の整数: {hours_ahead}")
        params = self._common_params()
        # forecast API は cnt で件数指定 (1 件 3 時間)
        cnt = max(1, min(40, (hours_ahead + 2) // 3))
        params["cnt"] = cnt
        payload = self._call(OPENWEATHER_FORECAST_URL, params)
        try:
            items = payload["list"]
            location_label = payload.get("city", {}).get("name", "")
        except (KeyError, TypeError) as e:
            raise OpenWeatherResponseError(
                f"OpenWeather forecast レスポンスが不正: {e}"
            ) from e
        return [
            WeatherSnapshot.from_openweather_forecast_item(item, location_label=location_label)
            for item in items
        ]

    # -- internal ----------------------------------------------------------

    def _common_params(self) -> dict[str, Any]:
        return {
            "lat": self.lat,
            "lon": self.lon,
            "appid": self.api_key,
            "units": DEFAULT_UNITS,
            "lang": DEFAULT_LANG,
        }

    def _call(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        try:
            resp = self.http_client.get(url, params=params, timeout=self.timeout)
        except Exception as e:
            raise OpenWeatherNetworkError(f"OpenWeather API ネットワークエラー: {e}") from e

        status = resp.status_code
        if status == 401:
            raise OpenWeatherAuthError(
                f"OpenWeather API 認証失敗 (status=401)。`OPENWEATHER_API_KEY` を確認"
            )
        if status >= 400:
            try:
                body = resp.text
            except Exception:
                body = "<unreadable>"
            raise OpenWeatherError(
                f"OpenWeather API HTTP エラー (status={status}): {body[:200]}"
            )
        try:
            data = resp.json()
        except (ValueError, json.JSONDecodeError) as e:
            raise OpenWeatherResponseError(f"OpenWeather API JSON パース失敗: {e}") from e
        if not isinstance(data, dict):
            raise OpenWeatherResponseError(
                f"OpenWeather API は dict を期待するが {type(data).__name__} を受領"
            )
        return data
