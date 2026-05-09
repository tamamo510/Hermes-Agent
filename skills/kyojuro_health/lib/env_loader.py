"""kyojuro_health.lib.env_loader — 環境変数から API キーを読み込む。

CLAUDE.md ルール 17:
  > キーの値をコードにハードコードするな。環境変数で読め。.env は .gitignore に入れろ

このモジュールは環境変数の取得を一箇所に集約する。
- 取得失敗時は MissingEnvVarError を上げて、温子に「.env を確認してください」と促す
- テストでは `monkeypatch.setenv()` で値を注入する
- 実装コードに API キーの値を直書きしない (CLAUDE.md ルール 17 厳守)

OpenWeatherMap の API キーは Drive 「俺たちの家」直下 `secrets_20260508.md` で温子が管理し、
Indigo 搬入時に環境変数 `OPENWEATHER_API_KEY` として注入する運用。
"""

from __future__ import annotations

import os
from typing import Optional


# 環境変数名定数 (実装コードから値ではなく **キー名** だけを参照する)
ENV_OPENWEATHER_API_KEY = "OPENWEATHER_API_KEY"
ENV_OPENWEATHER_LAT = "OPENWEATHER_LAT"  # default: 玉造 (大阪市天王寺区) 緯度
ENV_OPENWEATHER_LON = "OPENWEATHER_LON"  # default: 玉造 (大阪市天王寺区) 経度

# デフォルト座標 (大阪市天王寺区玉造、温子と杏寿郎の家、発注書 §3-5)
DEFAULT_LAT = "34.6724"
DEFAULT_LON = "135.5325"


class MissingEnvVarError(RuntimeError):
    """環境変数が設定されていない。.env を確認するよう温子に促す。"""

    def __init__(self, var_name: str, hint: Optional[str] = None) -> None:
        msg = (
            f"環境変数 {var_name} が設定されていません。"
            f"`.env` ファイルを確認してください "
            f"(Drive 「俺たちの家」直下 secrets_20260508.md に値があります)。"
        )
        if hint:
            msg = f"{msg} ヒント: {hint}"
        super().__init__(msg)
        self.var_name = var_name


def get_openweather_api_key(env: Optional[dict[str, str]] = None) -> str:
    """`OPENWEATHER_API_KEY` を環境変数から取得する。

    Args:
        env: テスト用に環境変数辞書を注入できる (デフォルトは os.environ)。

    Returns:
        API キー文字列。

    Raises:
        MissingEnvVarError: 環境変数が未設定 or 空文字。
    """
    if env is None:
        env = os.environ
    value = env.get(ENV_OPENWEATHER_API_KEY, "").strip()
    if not value:
        raise MissingEnvVarError(
            ENV_OPENWEATHER_API_KEY,
            hint="OpenWeatherMap (https://openweathermap.org/) で取得した API キー",
        )
    return value


def get_openweather_coordinates(
    env: Optional[dict[str, str]] = None,
) -> tuple[float, float]:
    """`OPENWEATHER_LAT` / `OPENWEATHER_LON` を取得する。未設定時はデフォルト (玉造) を返す。"""
    if env is None:
        env = os.environ
    lat_str = env.get(ENV_OPENWEATHER_LAT, DEFAULT_LAT).strip() or DEFAULT_LAT
    lon_str = env.get(ENV_OPENWEATHER_LON, DEFAULT_LON).strip() or DEFAULT_LON
    try:
        return float(lat_str), float(lon_str)
    except ValueError as e:
        raise MissingEnvVarError(
            f"{ENV_OPENWEATHER_LAT}/{ENV_OPENWEATHER_LON}",
            hint=f"緯度経度は数値である必要がある (lat={lat_str!r}, lon={lon_str!r})",
        ) from e
