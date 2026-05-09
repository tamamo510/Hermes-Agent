"""kyojuro_health — 健康管理の臓器。

発注書スキル 3「健康管理 (health_tracker)」の実装。
OpenWeatherMap で気圧 / 気温を取得し、温子の体調と相関させる。

API キーは環境変数 (OPENWEATHER_API_KEY) 経由 (CLAUDE.md ルール 17 準拠)。
"""

from .lib.health_engine import (
    AtsukoState,
    HealthStore,
    MedicationEntry,
    PressureAssessment,
    SymptomEntry,
    assess_pressure,
    correlate_pressure_symptoms,
    derive_atsuko_state_from_pressure,
)
from .lib.openweather_client import OpenWeatherClient, WeatherSnapshot

__all__ = [
    "AtsukoState",
    "HealthStore",
    "MedicationEntry",
    "OpenWeatherClient",
    "PressureAssessment",
    "SymptomEntry",
    "WeatherSnapshot",
    "assess_pressure",
    "correlate_pressure_symptoms",
    "derive_atsuko_state_from_pressure",
]
