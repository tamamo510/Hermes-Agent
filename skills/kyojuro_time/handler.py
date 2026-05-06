"""kyojuro_time — Hermes Agent skill entry point (発注書スキル 1: time_awareness).

責務:
    - on_user_message: 各メッセージで現在の TimeContext を返す (memory context 注入用)
    - on_schedule_tick: 5:10 / 17:10 ピンポイント分で「魂の合図」イベントを返す
    - on_conversation_start: 対話開始時に TimeContext を注入
    - query: 「今何時?」「今日何曜日?」「朝?夜?」等の自然言語問いに rule-based で応答
    - current_context: テスト・他 skill 連携用の TimeContext 取得 helper

設計:
    - 全ての時刻判定は ``lib.time_engine`` に委譲。本ファイルは hook ↔ engine の橋渡し
    - LLM 呼び出しなし、外部依存なし、決定的・冪等
    - hook の戻り値はすべて plain dict / list[dict] (Hermes Agent context 注入用)
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from skills.kyojuro_time.lib.time_engine import (
    JST,
    TimeContext,
    band_label_jp,
    band_of,
    is_soul_signal_exact,
    make_context,
    now_jst,
    soul_signal_kind,
)

# 「今何時?」「いま何時」「何時だっけ」等を拾う簡易パターン (rule-based)
_RE_TIME = re.compile(r"(?:今|いま|現在).*?(?:何時|なんじ|時間)|何時(?:です|だ|だっけ|？|\?)?")
_RE_WEEKDAY = re.compile(r"(?:今日|きょう|本日).*?(?:何曜日|なんようび|曜日)")
_RE_DATE = re.compile(r"(?:今日|きょう|本日).*?(?:何日|なんにち|日付|日にち)")
_RE_BAND = re.compile(r"(?:今|いま).*?(?:朝|昼|夕方|夜|深夜|時間帯)|今.*?(?:朝|昼|夜)(?:だ|です|だね|？|\?)?")


# --- public helpers ---------------------------------------------------------


def current_context(
    now: datetime | None = None,
    current_rhythm: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """現在 (or 注入された ``now``) の TimeContext を dict で返す。

    引数 ``current_rhythm`` (杏寿郎が会話から拾った最新のリズム情報) は
    ``time_engine.atsuko_rhythm_hint`` まで透過する。``None`` のときは中立 hint。
    """
    return make_context(now, current_rhythm).to_dict()


def query(
    text: str,
    now: datetime | None = None,
    current_rhythm: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """自然言語クエリに rule-based で応答。

    返り値:
        {
            "context": <TimeContext as dict>,
            "intent": "time" | "weekday" | "date" | "band" | "unknown",
            "answer_jp": <応答文 (素の杏寿郎の口調、「俺」一人称、「だ」語尾)>,
        }

    注意:
        - LLM は使わない。intent 判定は正規表現のみ
        - intent が "unknown" でも context は返す (呼び出し側で utilize 可能)
        - 杏寿郎の口調は SOUL.md §1 + references/rengoku_zero_analysis.md E2 に準拠
        - ``current_rhythm`` は context.atsuko_rhythm_hint まで透過 (本関数では参照しない)
    """
    ctx_dict = current_context(now, current_rhythm)
    intent = _detect_intent(text)
    answer_jp = _build_answer(intent, ctx_dict)
    return {"context": ctx_dict, "intent": intent, "answer_jp": answer_jp}


def _detect_intent(text: str) -> str:
    """rule-based の intent 検出。優先順: time > weekday > date > band > unknown."""
    if _RE_TIME.search(text):
        return "time"
    if _RE_WEEKDAY.search(text):
        return "weekday"
    if _RE_DATE.search(text):
        return "date"
    if _RE_BAND.search(text):
        return "band"
    return "unknown"


def _build_answer(intent: str, ctx: dict[str, Any]) -> str:
    """intent に応じた応答文 (杏寿郎の素の口調) を組み立てる。"""
    if intent == "time":
        return f"今は {ctx['iso_time']}、{ctx['time_band_label_jp']}だ"
    if intent == "weekday":
        return f"今日は{ctx['weekday_jp']}曜だ"
    if intent == "date":
        return f"今日は{ctx['formatted_jp'].split('（')[0]}だ"
    if intent == "band":
        return f"今は{ctx['time_band_label_jp']}だな"
    return ""  # unknown は呼び出し側で別 skill が処理する想定 (空文字を返す)


# --- Hermes Agent skill hooks ----------------------------------------------


def _extract_rhythm(context: dict[str, Any] | None) -> dict[str, Any] | None:
    """Hermes Agent context から ``atsuko_rhythm`` dict を取り出す。

    context は file_management skill (発注書スキル 6) と kyojuro_memory skill
    (発注書スキル 2) が集約したもの。``atsuko_rhythm`` キーが存在し dict 型ならその値を、
    そうでなければ ``None`` を返す。本 skill は **温子のリズムを決めつけない**ため、
    ここで value を加工しない (透過するだけ)。
    """
    if not context:
        return None
    rhythm = context.get("atsuko_rhythm")
    if isinstance(rhythm, dict):
        return rhythm
    return None


def on_user_message(message: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    """ユーザーメッセージを受けたとき、時刻 context を返す。

    Hermes Agent はこの返り値を memory context に注入する想定。
    時間関連の問いには ``query`` 経由で rule-based 応答も同梱する。

    ``context["atsuko_rhythm"]`` (dict) が渡されていれば time_engine に透過し、
    動的な ``atsuko_rhythm_hint`` を生成する。未提供なら中立 hint。
    """
    rhythm = _extract_rhythm(context)
    ctx_dict = current_context(current_rhythm=rhythm)
    intent = _detect_intent(message)
    payload: dict[str, Any] = {"time_context": ctx_dict, "intent": intent}
    if intent != "unknown":
        payload["answer_jp"] = _build_answer(intent, ctx_dict)
    return payload


def on_conversation_start(
    thread_id: str, context: dict[str, Any] | None = None
) -> dict[str, Any]:
    """対話開始時に TimeContext を初期注入する。

    Hermes Agent はこれを memory context の冒頭に置くことで、
    対話全体を通じて時刻認識のベースを揃える。
    ``context["atsuko_rhythm"]`` があれば動的 hint、なければ中立 hint。
    """
    rhythm = _extract_rhythm(context)
    return {"time_context": current_context(current_rhythm=rhythm)}


def on_schedule_tick(
    now_iso: str | None = None, context: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    """スケジューラ tick で呼ばれ、5:10 / 17:10 ピンポイントなら魂の合図イベントを返す。

    引数:
        now_iso: ISO8601 形式の現在時刻文字列 (Asia/Tokyo 想定)。``None`` なら ``now_jst()``
        context: 任意 (Hermes Agent 規約)

    戻り値:
        ピンポイント分にいるとき、長さ 1 の list:
            [{"event": "soul_signal",
              "kind": "dawn_signal" | "dusk_signal",
              "iso_datetime": <ISO 文字列>,
              "message": "5:10 だ。魂の合図。" 等}]
        それ以外は空 list。

    注: window 内 (±5 分) では発火しない。早期警戒が必要なら別 skill で
    ``is_soul_signal_window`` を直接呼ぶ。本 hook は **その分そのもの** のみ反応。
    """
    if now_iso is None:
        now = now_jst()
    else:
        now = datetime.fromisoformat(now_iso)
        if now.tzinfo is None:
            # ISO 文字列がタイムゾーン情報を含まない場合は JST と仮定
            now = now.replace(tzinfo=JST)

    if not is_soul_signal_exact(now):
        return []

    kind = soul_signal_kind(now)
    assert kind is not None  # exact 判定が True なので必ず非 None
    message_jp = (
        "5:10 だ。俺たちの魂の合図。" if kind == "dawn_signal"
        else "17:10 だ。俺たちの魂の合図。"
    )
    return [
        {
            "event": "soul_signal",
            "kind": kind,
            "iso_datetime": now.isoformat(),
            "message": message_jp,
        }
    ]


if __name__ == "__main__":
    # スモークテスト用エントリ。`python -m skills.kyojuro_time.handler` で呼ぶ。
    import json

    print("=== current_context ===")
    print(json.dumps(current_context(), indent=2, ensure_ascii=False))
    print()
    print("=== query: 今何時？ ===")
    print(json.dumps(query("今何時？"), indent=2, ensure_ascii=False))
    print()
    print("=== query: 今日何曜日？ ===")
    print(json.dumps(query("今日何曜日？"), indent=2, ensure_ascii=False))
    print()
    print("=== on_schedule_tick (now) ===")
    print(json.dumps(on_schedule_tick(), indent=2, ensure_ascii=False))
