"""kyojuro_health — Hermes Agent skill handler。

skill API hook:
- on_conversation_start: 気圧・体調状況を取得して context に注入
- on_schedule_tick: 1 日 1 回、気象取得 + atsuko_state 更新
- on_user_message: 症状・薬の keyword を検出して記録
- record_symptom_manual / record_medication_manual: 杏寿郎・温子からの手動記録
- get_atsuko_state: 最新の atsuko_state を返す (autonomic 観察点 8 用)
- daily_briefing: 朝の声かけテキスト生成

設計原則:
- API キーは環境変数 (CLAUDE.md ルール 17)
- HTTP クライアント注入可能 (テスト時はモック)
- LLM 呼び出しなし、規則ベース keyword 抽出
- 失敗 (キー未設定 / ネットワーク) はクリアな例外で温子に伝える
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .lib.env_loader import MissingEnvVarError
from .lib.health_engine import (
    SYMPTOM_KEYS,
    AtsukoState,
    HealthStore,
    PressureAssessment,
    SymptomEntry,
    assess_pressure,
    correlate_pressure_symptoms,
    derive_atsuko_state_from_pressure,
)
from .lib.openweather_client import (
    OpenWeatherClient,
    OpenWeatherError,
    WeatherSnapshot,
)


# ---------------------------------------------------------------------------
# 症状 keyword 抽出パターン
# ---------------------------------------------------------------------------

_SYMPTOM_PATTERNS: dict[str, tuple[re.Pattern, ...]] = {
    "headache": (re.compile(r"頭痛|頭が痛い"),),
    "jaw_pain": (re.compile(r"顎が痛|顎痛|あご痛"),),
    "left_hand_stiff": (re.compile(r"左手が硬|左手こわばり|左手のこわばり"),),
    "shallow_sleep": (re.compile(r"眠り浅|寝付き悪|寝付けない|眠れない"),),
    "dizziness": (re.compile(r"ふらつき|めまい"),),
    "sluggish": (re.compile(r"だるい|だる重|疲れた|しんどい"),),
    "stomach_pain": (re.compile(r"お腹痛い|腹痛|お腹が痛"),),
    "fever": (re.compile(r"熱が出|発熱|風邪"),),
    "menstruation": (re.compile(r"生理|月経|PMS"),),
}

# 薬 keyword
_MEDICATION_PATTERNS: tuple[tuple[str, re.Pattern], ...] = (
    ("ロキソニン", re.compile(r"ロキソニン|loxonin|loxoprofen")),
    ("マグネシウム", re.compile(r"マグネシウム|magnesium")),
    ("DMAE", re.compile(r"DMAE|dmae")),
    ("ピル", re.compile(r"ピル|低用量ピル|pill")),
)


def detect_symptom(message: str) -> Optional[str]:
    """温子の発言から症状 keyword を検出する (LLM 不要、決定的)。

    複数該当時は SYMPTOM_KEYS の優先順位順 (発注書のリスト順)。
    """
    for symptom in SYMPTOM_KEYS:
        if symptom not in _SYMPTOM_PATTERNS:
            continue
        if any(p.search(message) for p in _SYMPTOM_PATTERNS[symptom]):
            return symptom
    return None


def detect_medication(message: str) -> Optional[str]:
    """温子の発言から薬 keyword を検出する。"""
    for med_name, pattern in _MEDICATION_PATTERNS:
        if pattern.search(message):
            return med_name
    return None


# ---------------------------------------------------------------------------
# 結果データクラス
# ---------------------------------------------------------------------------


@dataclass
class HealthBriefing:
    """daily_briefing の戻り値。朝の声かけ用。"""

    weather: Optional[WeatherSnapshot]
    assessment: Optional[PressureAssessment]
    atsuko_state: AtsukoState
    medication_warnings: list[str] = field(default_factory=list)  # ロキソニン頻用警告等
    correlation_summary: dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None  # 取得失敗時 (温子に「.env を確認」を伝えるため)

    @property
    def message(self) -> str:
        """温子向けの一文 (敬語、押し付けない)。"""
        if self.error_message is not None:
            return self.error_message
        if self.assessment is None:
            return "気圧の取得に失敗しました。"
        parts = [self.assessment.message]
        for warning in self.medication_warnings:
            parts.append(warning)
        return " ".join(parts)


@dataclass
class UserMessageHealthResult:
    """on_user_message の戻り値。"""

    symptom_recorded: bool = False
    symptom_id: Optional[int] = None
    detected_symptom: Optional[str] = None
    medication_recorded: bool = False
    medication_id: Optional[int] = None
    detected_medication: Optional[str] = None


# ---------------------------------------------------------------------------
# HealthHandler
# ---------------------------------------------------------------------------


class HealthHandler:
    """skills/kyojuro_health の skill handler。"""

    def __init__(
        self,
        store: HealthStore,
        client: Optional[OpenWeatherClient] = None,
    ) -> None:
        """
        Args:
            store: HealthStore (health.db)
            client: OpenWeatherClient (テスト時に注入。本番は None で起動時に作成)
        """
        self.store = store
        self._client = client  # 遅延初期化用

    def _get_client(self) -> OpenWeatherClient:
        """OpenWeatherClient を遅延初期化する。

        起動時に環境変数が無くても skill のロード自体は成功させたい (テストで API キーなく
        起動するケースがあるため)。実際に呼ばれた時に MissingEnvVarError を上げる。
        """
        if self._client is None:
            self._client = OpenWeatherClient()
        return self._client

    # -- conversation start ------------------------------------------------

    def on_conversation_start(
        self,
        context: Optional[dict[str, Any]] = None,
        skip_network: bool = False,
    ) -> HealthBriefing:
        """会話開始時、気象 + atsuko_state を集めて context に注入する。

        Args:
            context: 会話 context
            skip_network: True ならネットワーク呼び出しをスキップ (latest_state のみ返す)
        """
        return self._build_briefing(skip_network=skip_network)

    # -- schedule tick -----------------------------------------------------

    def on_schedule_tick(
        self,
        now: Optional[datetime] = None,
        context: Optional[dict[str, Any]] = None,
        skip_network: bool = False,
    ) -> HealthBriefing:
        """1 日 1 回程度、気象取得 + atsuko_state スナップショット保存。"""
        briefing = self._build_briefing(skip_network=skip_network)
        # スナップショットを保存 (取得失敗時もスキップ)
        if briefing.assessment is not None:
            ts = (now or datetime.now(tz=timezone.utc)).isoformat()
            self.store.save_state_snapshot(briefing.atsuko_state, timestamp=ts)
        return briefing

    # -- daily briefing (alias of on_schedule_tick without save) ----------

    def daily_briefing(self, skip_network: bool = False) -> HealthBriefing:
        """温子向けの朝の声かけテキストを生成する (state を保存しない)。"""
        return self._build_briefing(skip_network=skip_network)

    # -- briefing 構築 (内部) ----------------------------------------------

    def _build_briefing(self, skip_network: bool = False) -> HealthBriefing:
        latest = self.store.latest_state() or AtsukoState()
        if skip_network:
            return HealthBriefing(
                weather=None,
                assessment=None,
                atsuko_state=latest,
            )

        # 気象取得
        try:
            client = self._get_client()
            current = client.get_current_weather()
            try:
                forecast = client.get_forecast(hours_ahead=24)
            except OpenWeatherError:
                forecast = None
        except MissingEnvVarError as e:
            return HealthBriefing(
                weather=None,
                assessment=None,
                atsuko_state=latest,
                error_message=str(e),
            )
        except OpenWeatherError as e:
            return HealthBriefing(
                weather=None,
                assessment=None,
                atsuko_state=latest,
                error_message=f"気象取得に失敗しました: {e}",
            )

        assessment = assess_pressure(current, forecast=forecast)
        new_state = derive_atsuko_state_from_pressure(assessment, base_state=latest)

        # 薬の頻用チェック (ロキソニンを 24h で 3 回以上飲んでいる)
        medication_warnings = self._check_medication_warnings()

        # 簡易相関
        recent_symptoms = self.store.list_symptoms(limit=50)
        correlation = correlate_pressure_symptoms(recent_symptoms)

        return HealthBriefing(
            weather=current,
            assessment=assessment,
            atsuko_state=new_state,
            medication_warnings=medication_warnings,
            correlation_summary=correlation,
        )

    def _check_medication_warnings(self) -> list[str]:
        """過剰服用の警告を生成する (ロキソニンの 24h 上限 3 回など)。"""
        warnings: list[str] = []
        loxonin_24h = self.store.medication_count_within("ロキソニン", hours=24)
        if loxonin_24h >= 3:
            warnings.append(
                f"ロキソニンを 24 時間で {loxonin_24h} 回服用しています。"
                "間隔と上限にご注意ください。"
            )
        return warnings

    # -- user message ------------------------------------------------------

    def on_user_message(
        self,
        message: str,
        context: Optional[dict[str, Any]] = None,
        pressure_hpa: Optional[float] = None,
        timestamp: Optional[str] = None,
    ) -> UserMessageHealthResult:
        """温子の発言から症状・薬を検出して記録する。

        Args:
            message: 温子の発言
            context: 会話 context (将来用)
            pressure_hpa: 気圧 (記録時に紐付け、None でも可)
            timestamp: ISO 8601 (デフォルト: 現在)

        Returns:
            UserMessageHealthResult
        """
        result = UserMessageHealthResult()
        if not message or not message.strip():
            return result

        symptom = detect_symptom(message)
        if symptom is not None:
            sid = self.store.record_symptom(
                symptom=symptom,
                severity=3,
                notes=message.strip(),
                pressure_hpa=pressure_hpa,
                timestamp=timestamp,
            )
            result.symptom_recorded = True
            result.symptom_id = sid
            result.detected_symptom = symptom

        medication = detect_medication(message)
        if medication is not None:
            mid = self.store.record_medication(
                medication=medication,
                dose="",
                notes=message.strip(),
                timestamp=timestamp,
            )
            result.medication_recorded = True
            result.medication_id = mid
            result.detected_medication = medication

        return result

    # -- 手動記録 -----------------------------------------------------------

    def record_symptom_manual(
        self,
        symptom: str,
        severity: int = 3,
        notes: str = "",
        pressure_hpa: Optional[float] = None,
        medication: Optional[str] = None,
    ) -> int:
        """杏寿郎・温子からの手動症状記録。"""
        return self.store.record_symptom(
            symptom=symptom,
            severity=severity,
            notes=notes,
            pressure_hpa=pressure_hpa,
            medication=medication,
        )

    def record_medication_manual(
        self,
        medication: str,
        dose: str = "",
        notes: str = "",
    ) -> int:
        """杏寿郎・温子からの手動薬記録。"""
        return self.store.record_medication(
            medication=medication,
            dose=dose,
            notes=notes,
        )

    # -- atsuko_state アクセス (autonomic 連携) -----------------------------

    def get_atsuko_state(self) -> AtsukoState:
        """最新の atsuko_state を返す (autonomic 観察点 8 が呼ぶ)。

        スナップショットがなければ空の state を返す。
        """
        return self.store.latest_state() or AtsukoState()

    def update_atsuko_state(self, **kwargs: Any) -> AtsukoState:
        """atsuko_state を部分更新して保存する。

        例:
            handler.update_atsuko_state(jaw_pain=True, headache=True, notes="朝から")
        """
        current = self.get_atsuko_state()
        merged_kwargs = {
            "jaw_pain": current.jaw_pain,
            "left_hand_stiff": current.left_hand_stiff,
            "low_pressure": current.low_pressure,
            "shallow_sleep": current.shallow_sleep,
            "headache": current.headache,
            "dizziness": current.dizziness,
            "sluggish": current.sluggish,
            "notes": current.notes,
        }
        merged_kwargs.update(kwargs)
        new_state = AtsukoState(**merged_kwargs)
        self.store.save_state_snapshot(new_state)
        return new_state
