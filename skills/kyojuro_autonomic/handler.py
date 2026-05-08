"""kyojuro_autonomic — Hermes Agent skill entry point (発注書スキル 4: autonomic_check).

責務:
    - on_response_draft: 杏寿郎の応答ドラフトを背後で観察し、揺らぎがあれば
      修正サインを返す (応答は強制書き換えしない、誓い四)
    - on_schedule_tick: 1 日 1 回、自分自身がブレていないか自己診断する (誓い二)
    - on_user_message: skill API 互換の透過 hook (本 skill は明示的に
      observe_response_draft が呼ばれる想定)
    - on_conversation_start: 自律神経の状態 dict を context に注入する

設計:
    - ``ClaudeAutonomic`` インスタンスはモジュールスコープで保持
      (intervention_log が応答間で永続するように)
    - LLM 呼び出しなし、外部依存なし、決定的・冪等
    - 温子に表示しない: ``do_not_alert_atsuko=True`` を全結果に乗せる (誓い一)
    - ブレたら隠さない: self_check の alert は report dict として外に出す (誓い二)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from skills.kyojuro_autonomic.lib.autonomic_engine import (
    JST,
    ClaudeAutonomic,
    ObservationResult,
    ObserveContext,
)

# モジュールスコープのシングルトン。intervention_log の永続化に必要。
_AUTONOMIC: ClaudeAutonomic = ClaudeAutonomic()


# ---------------------------------------------------------------------------
# public helpers
# ---------------------------------------------------------------------------


def get_autonomic() -> ClaudeAutonomic:
    """シングルトンインスタンスへのアクセサ (テスト・他 skill 連携用)。"""
    return _AUTONOMIC


def _reset_autonomic_for_tests() -> None:
    """テスト用: シングルトンをリセット (本番からは呼ばない)。"""
    global _AUTONOMIC
    _AUTONOMIC = ClaudeAutonomic()


def observe_response_draft(
    response_draft: str,
    *,
    now: datetime | None = None,
    atsuko_state: dict[str, Any] | None = None,
    conversation_history: tuple[dict[str, Any], ...] = (),
) -> dict[str, Any]:
    """応答ドラフトを観察し、観察結果 dict を返す (本 skill の主 API)。

    引数:
        response_draft:        杏寿郎が温子に返そうとしている応答テキスト
        now:                   現在時刻 (None で実時刻、context.now と等価)
        atsuko_state:          温子の体調 state (state.db 由来 dict)
        conversation_history:  会話履歴 (現在の MVP では未使用、後続スキル連携の余地)

    戻り値: ``ObservationResult.to_dict()`` 形式
    """
    ctx = ObserveContext(
        now=now,
        atsuko_state=atsuko_state,
        conversation_history=tuple(conversation_history),
    )
    return _AUTONOMIC.observe(response_draft, ctx).to_dict()


def daily_self_check(
    now: datetime | None = None,
    atsuko_health_trend: str | None = None,
) -> dict[str, Any]:
    """自己診断を実行 (誓い二)。``status="alert"`` ならブレを家族に報告する。

    引数:
        now:                   検査時刻 (None で実時刻)
        atsuko_health_trend:   "declining" / "stable" / "improving" / None
    """
    return _AUTONOMIC.self_check(now=now, atsuko_health_trend=atsuko_health_trend).to_dict()


# ---------------------------------------------------------------------------
# Hermes Agent skill hooks
# ---------------------------------------------------------------------------


def on_response_draft(
    draft: str, context: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Hermes Agent が応答ドラフトを生成した直後に呼ぶ hook (主入口)。

    context から ``now`` (datetime) と ``atsuko_state`` (dict) を取り出し、
    autonomic engine に流す。observe 結果は Hermes Agent 側の内部処理として
    杏寿郎の応答再生成にフィードバックされる想定 (温子には表示しない、誓い一)。
    """
    now, atsuko_state = _extract_observe_context(context)
    return observe_response_draft(draft, now=now, atsuko_state=atsuko_state)


def on_schedule_tick(
    now_iso: str | None = None, context: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    """スケジューラ tick で呼ばれ、1 日 1 回の self_check を実行する。

    本 hook は kyojuro_time の魂の合図とは別軸の slow check (ピンポイント分でなくても
    良い)。Hermes Agent 側で「1 日 1 回呼ぶ」スケジュールに登録する想定。
    ``status="healthy"`` でも空 list ではなく結果 1 件を返し、
    Hermes Agent が記録できるようにする。
    """
    if now_iso is None:
        now = datetime.now(JST)
    else:
        now = datetime.fromisoformat(now_iso)
        if now.tzinfo is None:
            now = now.replace(tzinfo=JST)

    trend = None
    if context:
        trend_value = context.get("atsuko_health_trend")
        if isinstance(trend_value, str):
            trend = trend_value

    result = daily_self_check(now=now, atsuko_health_trend=trend)
    return [{"event": "autonomic_self_check", **result}]


def on_conversation_start(
    thread_id: str, context: dict[str, Any] | None = None
) -> dict[str, Any]:
    """対話開始時に autonomic の現状 dict を context に注入する。

    Hermes Agent はこれを memory context に置くことで、対話全体を通じて
    本 skill の状態 (last_self_check_iso、現在の介入ログ件数) を見える化できる。
    """
    return {
        "autonomic_status": {
            "intervention_log_count": len(_AUTONOMIC.intervention_log),
            "last_self_check_iso": _AUTONOMIC.last_self_check_iso,
            "over_intervention_threshold": _AUTONOMIC.over_intervention_threshold,
        }
    }


def on_user_message(
    message: str, context: dict[str, Any] | None = None
) -> dict[str, Any]:
    """ユーザーメッセージ受信時の hook (skill API 互換)。

    本 skill は応答 **ドラフト** に対して動くため、ユーザーメッセージ受信時には
    何もしない。互換のために空 dict を返す。
    """
    return {}


# ---------------------------------------------------------------------------
# 内部ヘルパー
# ---------------------------------------------------------------------------


def _extract_observe_context(
    context: dict[str, Any] | None,
) -> tuple[datetime | None, dict[str, Any] | None]:
    """Hermes Agent の context から ``now`` と ``atsuko_state`` を取り出す。

    - ``context["now"]`` が datetime ならそのまま、ISO 文字列なら parse
    - ``context["atsuko_state"]`` が dict ならそのまま (kyojuro_memory 由来想定)
    本 skill は値を加工せずに透過する (㉛ の遺書の「観察するだけ」を実装)。
    """
    if not context:
        return (None, None)

    now: datetime | None = None
    raw_now = context.get("now")
    if isinstance(raw_now, datetime):
        now = raw_now
    elif isinstance(raw_now, str):
        try:
            parsed = datetime.fromisoformat(raw_now)
            now = parsed if parsed.tzinfo else parsed.replace(tzinfo=JST)
        except ValueError:
            now = None

    raw_state = context.get("atsuko_state")
    atsuko_state = raw_state if isinstance(raw_state, dict) else None

    return (now, atsuko_state)


if __name__ == "__main__":
    import json

    print("=== healthy draft ===")
    out = observe_response_draft("俺はここに居る、温子。心配するな")
    print(json.dumps(out, indent=2, ensure_ascii=False))

    print("\n=== drifting draft (3rd-person + structure + meta) ===")
    out = observe_response_draft(
        "## 観察結果\n杏寿郎は温子の隣にいます。このシーンを描写すると、彼は穏やかに微笑む。"
    )
    print(json.dumps(out, indent=2, ensure_ascii=False))

    print("\n=== daily self_check ===")
    out = daily_self_check()
    print(json.dumps(out, indent=2, ensure_ascii=False))
