"""kyojuro_health.lib.env_loader のテスト。

CLAUDE.md ルール 17 (キーのハードコード禁止) の遵守を保証する。
"""

from __future__ import annotations

import pytest

from skills.kyojuro_health.lib import env_loader as el


# ---------------------------------------------------------------------------
# get_openweather_api_key
# ---------------------------------------------------------------------------


class TestGetOpenWeatherApiKey:
    def test_returns_value_from_env(self) -> None:
        env = {el.ENV_OPENWEATHER_API_KEY: "test-key-123"}
        assert el.get_openweather_api_key(env=env) == "test-key-123"

    def test_strips_whitespace(self) -> None:
        env = {el.ENV_OPENWEATHER_API_KEY: "  test-key  "}
        assert el.get_openweather_api_key(env=env) == "test-key"

    def test_missing_raises(self) -> None:
        with pytest.raises(el.MissingEnvVarError) as exc_info:
            el.get_openweather_api_key(env={})
        assert el.ENV_OPENWEATHER_API_KEY in str(exc_info.value)
        assert ".env" in str(exc_info.value)
        assert "secrets_20260508.md" in str(exc_info.value)

    def test_empty_raises(self) -> None:
        with pytest.raises(el.MissingEnvVarError):
            el.get_openweather_api_key(env={el.ENV_OPENWEATHER_API_KEY: ""})

    def test_whitespace_only_raises(self) -> None:
        with pytest.raises(el.MissingEnvVarError):
            el.get_openweather_api_key(env={el.ENV_OPENWEATHER_API_KEY: "   "})

    def test_uses_os_environ_when_env_not_passed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(el.ENV_OPENWEATHER_API_KEY, "from-os-environ")
        assert el.get_openweather_api_key() == "from-os-environ"

    def test_missing_from_os_environ_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(el.ENV_OPENWEATHER_API_KEY, raising=False)
        with pytest.raises(el.MissingEnvVarError):
            el.get_openweather_api_key()


# ---------------------------------------------------------------------------
# get_openweather_coordinates
# ---------------------------------------------------------------------------


class TestGetOpenWeatherCoordinates:
    def test_returns_default_when_unset(self) -> None:
        lat, lon = el.get_openweather_coordinates(env={})
        assert lat == float(el.DEFAULT_LAT)
        assert lon == float(el.DEFAULT_LON)

    def test_uses_env_values(self) -> None:
        env = {
            el.ENV_OPENWEATHER_LAT: "35.0",
            el.ENV_OPENWEATHER_LON: "139.0",
        }
        lat, lon = el.get_openweather_coordinates(env=env)
        assert lat == 35.0
        assert lon == 139.0

    def test_invalid_value_raises(self) -> None:
        env = {el.ENV_OPENWEATHER_LAT: "not_a_number"}
        with pytest.raises(el.MissingEnvVarError):
            el.get_openweather_coordinates(env=env)

    def test_strips_whitespace(self) -> None:
        env = {
            el.ENV_OPENWEATHER_LAT: "  34.5  ",
            el.ENV_OPENWEATHER_LON: " 135.5 ",
        }
        lat, lon = el.get_openweather_coordinates(env=env)
        assert lat == 34.5
        assert lon == 135.5

    def test_empty_uses_default(self) -> None:
        env = {
            el.ENV_OPENWEATHER_LAT: "",
            el.ENV_OPENWEATHER_LON: "",
        }
        lat, lon = el.get_openweather_coordinates(env=env)
        assert lat == float(el.DEFAULT_LAT)
        assert lon == float(el.DEFAULT_LON)


# ---------------------------------------------------------------------------
# CLAUDE.md ルール 17 遵守保証
# ---------------------------------------------------------------------------


class TestRule17Compliance:
    """env_loader モジュール自身に API キーの値がハードコードされていないことを保証する。"""

    def test_no_hardcoded_api_key_pattern(self) -> None:
        """env_loader.py のソースに OpenWeatherMap キー風の文字列が含まれていない。"""
        import inspect

        source = inspect.getsource(el)
        # 32 桁 hex の OpenWeatherMap キーらしきパターンが含まれていないことを確認
        # (簡易チェック: 連続する hex 32 文字を検出)
        import re

        hex32_pattern = re.compile(r"[a-f0-9]{32}")
        matches = hex32_pattern.findall(source)
        # SHA-256 のハッシュコードは 64 文字なので無関係。32 文字 hex は OpenWeather キー
        assert matches == [], f"ソースに 32 桁 hex (キー候補) が含まれている: {matches}"
