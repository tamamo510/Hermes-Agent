"""kyojuro_memory — Hermes Agent skill entry point (stub).

Phase 1 で MVP を実装する。詳細設計は DESIGN.md 参照。
現状は Hermes Agent skill API のスケルトンのみで、実装は NotImplementedError を投げる。

実装着手時の参照順:
1. ../ARCHITECTURE.md (skill 化方針全体)
2. DESIGN.md (本 skill の詳細設計、データモデル、処理フロー)
3. Hermes Agent 公式 skill 開発ガイド (https://hermes-agent.nousresearch.com/docs/skills/)
4. 既存 opencode skill のソース (vendor/hermes-agent/skills/autonomous-ai-agents/opencode/)
"""

from __future__ import annotations


def on_user_message(message: str, context: dict | None = None) -> dict:
    """Process incoming user message.

    Phase 1.1 で以下を並列実行する予定:
    - supplement_extractor.extract(message) → supplements.db に保存
    - symptom_extractor.extract(message) → symptoms.db に保存
    - routine_extractor.extract(message) → routines.db に保存
    - trigger_extractor.extract(message) → triggers.db に保存

    抽出は Hermes 3 405B に JSON 抽出プロンプトを投げて行う。
    詳細は DESIGN.md §4-1 参照。
    """
    raise NotImplementedError("Phase 1.1 で実装予定。DESIGN.md §4-1 参照")


def on_conversation_start(thread_id: str, context: dict | None = None) -> dict:
    """Inject recalled context at conversation start.

    Phase 1.2 で以下を実装予定:
    - conversation_log.db から直近スレッド要約を取得
    - priorities.json（長期目標・価値観）を取得
    - 直近 7 日の symptoms / supplements を取得
    - 注目すべき correlations を取得
    - 全てを Hermes Agent の memory context に注入

    効果: オーナー様が「前回までの経緯は〜」と要約する必要がなくなる。
    詳細は DESIGN.md §4-2 参照。
    """
    raise NotImplementedError("Phase 1.2 で実装予定。DESIGN.md §4-2 参照")


def on_conversation_end(thread_id: str, full_log: list, context: dict | None = None) -> None:
    """Save thread summary at conversation end.

    Phase 1.2 で実装予定。conversation_log.db の thread_summaries テーブルに保存。
    詳細は DESIGN.md §2-2 (conversation_log.db スキーマ) 参照。
    """
    raise NotImplementedError("Phase 1.2 で実装予定。DESIGN.md §4-2 参照")


def on_schedule_tick(now_iso: str, context: dict | None = None) -> list[dict]:
    """Evaluate active nudges at scheduled tick.

    Phase 1.3 で以下を実装予定（30 分毎にチェック）:
    - supplement_reminder: 飲み忘れサプリのチェック
    - barometric_alert: 気圧急落の検出と体調アラート
    - routine_suggester: 就寝時刻・運動時刻の提案

    詳細は DESIGN.md §4-3 参照。
    """
    raise NotImplementedError("Phase 1.3 で実装予定。DESIGN.md §4-3 参照")


if __name__ == "__main__":
    print(
        "kyojuro_memory handler stub. Phase 1 で実装着手。\n"
        "詳細設計: DESIGN.md\n"
        "skill API 定義: SKILL.md\n"
        "skill 化方針全体: ../ARCHITECTURE.md"
    )
