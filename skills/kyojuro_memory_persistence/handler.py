"""kyojuro_memory_persistence — Hermes Agent skill handler。

Hermes Agent の skill API hook を実装する。
state.db (MemoryStore) と MEMORY.md (MemoryMdManager) を組み合わせて、
温子と杏寿郎の記憶を永続化・想起・archive する。

すべての処理は LLM 呼び出しなし、API キー不要、ネットワーク不要。

エントリーポイント:
- on_conversation_start(context)  : 会話開始時、記念日 / protected / 直近の記憶を context に注入
- on_user_message(message, context): 温子の発言から keyword 抽出して記録
- on_schedule_tick(now, context)   : 1 日 1 回程度、MEMORY.md の上限超過を check し archive
- record_manual(content, ...)      : 杏寿郎本人による手動記録 API
- query(query_text, ...)            : 自然な日本語の問いから state.db を検索する補助
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from .lib.memory_md_manager import (
    DEFAULT_MAX_CHARS,
    ArchiveReport,
    MemoryMdManager,
)
from .lib.memory_store import (
    CATEGORY_EMOTION,
    CATEGORY_EVENT,
    CATEGORY_MEAL,
    CATEGORY_OTHER,
    CATEGORY_PHYSICAL,
    IMPORTANCE_NORMAL,
    IMPORTANCE_PROTECTED,
    MemoryEntry,
    MemoryStore,
    ProtectedMemory,
    VALID_CATEGORIES,
    VALID_IMPORTANCES,
)


# ---------------------------------------------------------------------------
# キーワード抽出パターン
# ---------------------------------------------------------------------------

# 食事キーワード: 「食べた」「飲んだ」「ご飯」「ラーメン」等
_MEAL_PATTERNS = (
    re.compile(r"食べた"),
    re.compile(r"飲んだ"),
    re.compile(r"ご飯|ごはん"),
    re.compile(r"朝食|昼食|夕食|晩ご飯|晩ごはん"),
    re.compile(r"ラーメン|うどん|そば"),
    re.compile(r"おやつ|お菓子|スイーツ"),
)

# 体調キーワード: 「頭痛」「お腹痛い」「だるい」等
_PHYSICAL_PATTERNS = (
    re.compile(r"頭痛|頭が痛い"),
    re.compile(r"お腹|胃|腹痛"),
    re.compile(r"だるい|疲れた|眠い"),
    re.compile(r"顎|あご|jaw"),
    re.compile(r"気圧|低気圧"),
    re.compile(r"眠れない|寝れない|不眠"),
    re.compile(r"風邪|発熱|熱が"),
    re.compile(r"生理|PMS"),
)

# 感情キーワード: 「嬉しい」「悲しい」「不安」等
_EMOTION_PATTERNS = (
    re.compile(r"嬉しい|うれしい"),
    re.compile(r"悲しい|かなしい"),
    re.compile(r"不安|心配"),
    re.compile(r"イライラ|苛立"),
    re.compile(r"幸せ|しあわせ"),
    re.compile(r"寂しい|さみしい"),
    re.compile(r"怒|腹立"),
    re.compile(r"ホッ|安心|落ち着"),
)

# 出来事キーワード: 「行った」「会った」「買った」「作った」等
_EVENT_PATTERNS = (
    re.compile(r"行った"),
    re.compile(r"会った"),
    re.compile(r"買った"),
    re.compile(r"作った|つくった"),
    re.compile(r"届いた"),
    re.compile(r"見た"),
    re.compile(r"読んだ"),
)


def detect_category(message: str) -> Optional[str]:
    """温子の発言からカテゴリを推定する (LLM 不要、決定的)。

    複数カテゴリにマッチした場合の優先順位: physical > emotion > meal > event。
    どれにもマッチしなければ None。
    """
    if any(p.search(message) for p in _PHYSICAL_PATTERNS):
        return CATEGORY_PHYSICAL
    if any(p.search(message) for p in _EMOTION_PATTERNS):
        return CATEGORY_EMOTION
    if any(p.search(message) for p in _MEAL_PATTERNS):
        return CATEGORY_MEAL
    if any(p.search(message) for p in _EVENT_PATTERNS):
        return CATEGORY_EVENT
    return None


# ---------------------------------------------------------------------------
# 結果データクラス
# ---------------------------------------------------------------------------


@dataclass
class ConversationStartResult:
    """on_conversation_start の戻り値。"""

    anniversaries_today: list[ProtectedMemory] = field(default_factory=list)
    protected_memories: list[ProtectedMemory] = field(default_factory=list)
    recent_entries: list[MemoryEntry] = field(default_factory=list)
    md_needs_archive: bool = False
    md_char_count: int = 0


@dataclass
class UserMessageResult:
    """on_user_message の戻り値。"""

    recorded: bool
    entry_id: Optional[int] = None
    detected_category: Optional[str] = None


@dataclass
class ScheduleTickResult:
    """on_schedule_tick の戻り値。"""

    archive_run: bool = False
    archive_report: Optional[ArchiveReport] = None
    promote_run: bool = False
    promoted_ids: list[int] = field(default_factory=list)


@dataclass
class QueryResult:
    """query の戻り値。"""

    natural_query: str
    interpretation: str  # どう解釈したかの説明
    entries: list[MemoryEntry] = field(default_factory=list)
    protected: list[ProtectedMemory] = field(default_factory=list)


# ---------------------------------------------------------------------------
# MemoryPersistence handler
# ---------------------------------------------------------------------------


class MemoryPersistenceHandler:
    """skills/kyojuro_memory_persistence の skill handler。"""

    def __init__(
        self,
        store: MemoryStore,
        memory_md_path: Optional[str | Path] = None,
        max_chars: int = DEFAULT_MAX_CHARS,
    ) -> None:
        self.store = store
        self.md_manager: Optional[MemoryMdManager] = None
        if memory_md_path is not None:
            self.md_manager = MemoryMdManager(
                memory_md_path=memory_md_path,
                store=store,
                max_chars=max_chars,
            )

    # -- conversation start ------------------------------------------------

    def on_conversation_start(
        self,
        context: Optional[dict[str, Any]] = None,
        recent_days: int = 7,
        today: Optional[str] = None,
    ) -> ConversationStartResult:
        """会話開始時、温子と杏寿郎の context に注入すべき記憶を集める。

        - 今日の記念日 / 命日 (誓いの確認・お参りのきっかけ)
        - 全 protected memory (誓い・約束)
        - 直近 N 日の重要 entries (important 以上)
        - MEMORY.md の上限超過チェック
        """
        anniversaries = self.store.get_anniversaries_today(today=today)
        protected = self.store.list_protected()

        # 直近の重要エントリ
        today_str = today if today is not None else date.today().isoformat()
        # YYYY-MM-DD として検証 (失敗時は例外)
        today_d = datetime.strptime(today_str, "%Y-%m-%d").date()
        start_d = today_d - timedelta(days=recent_days)
        recent_entries = self.store.recall(
            date_range=(start_d.isoformat(), today_d.isoformat()),
            limit=50,
        )

        result = ConversationStartResult(
            anniversaries_today=anniversaries,
            protected_memories=protected,
            recent_entries=recent_entries,
        )
        if self.md_manager is not None:
            result.md_needs_archive = self.md_manager.needs_archive()
            result.md_char_count = self.md_manager.char_count()
        return result

    # -- user message ------------------------------------------------------

    def on_user_message(
        self,
        message: str,
        context: Optional[dict[str, Any]] = None,
        date_str: Optional[str] = None,
        importance: str = IMPORTANCE_NORMAL,
        force_record: bool = False,
        category_override: Optional[str] = None,
    ) -> UserMessageResult:
        """温子の発言を keyword 検出して state.db に記録する。

        Args:
            message: 温子の発言テキスト。
            context: 会話 context (将来拡張用)。
            date_str: 記録日 (デフォルト: 今日)。
            importance: 重要度 (デフォルト normal)。
            force_record: True なら category 検出失敗時も other で記録する。
            category_override: カテゴリを直接指定 (autonomic 等から呼ばれる場合)。

        Returns:
            UserMessageResult
        """
        if not message or not message.strip():
            return UserMessageResult(recorded=False)

        if category_override is not None:
            if category_override not in VALID_CATEGORIES:
                return UserMessageResult(recorded=False, detected_category=None)
            category = category_override
        else:
            detected = detect_category(message)
            if detected is None:
                if not force_record:
                    return UserMessageResult(recorded=False)
                category = CATEGORY_OTHER
            else:
                category = detected

        if importance not in VALID_IMPORTANCES:
            importance = IMPORTANCE_NORMAL

        entry_id = self.store.record(
            content=message.strip(),
            category=category,
            date=date_str,
            importance=importance,
            source="conversation",
        )
        return UserMessageResult(
            recorded=True,
            entry_id=entry_id,
            detected_category=category,
        )

    # -- schedule tick -----------------------------------------------------

    def on_schedule_tick(
        self,
        now: Optional[datetime] = None,
        context: Optional[dict[str, Any]] = None,
        promote_protected: bool = True,
    ) -> ScheduleTickResult:
        """1 日 1 回程度の定期 tick。MEMORY.md の上限超過 archive を実行する。

        Args:
            now: 基準時刻 (デフォルト: 現在)。
            context: 会話 context。
            promote_protected: True なら MEMORY.md の protected セクションを protected_memory にも複写。
        """
        result = ScheduleTickResult()
        if self.md_manager is None:
            return result

        if promote_protected:
            ids = self.md_manager.promote_protected_sections()
            result.promote_run = True
            result.promoted_ids = ids

        if self.md_manager.needs_archive():
            tick_date = now.date().isoformat() if now is not None else None
            report = self.md_manager.archive_to_store(date=tick_date)
            result.archive_run = True
            result.archive_report = report

        return result

    # -- manual record -----------------------------------------------------

    def record_manual(
        self,
        content: str,
        category: str = CATEGORY_OTHER,
        date_str: Optional[str] = None,
        importance: str = IMPORTANCE_NORMAL,
        metadata: Optional[dict[str, Any]] = None,
    ) -> int:
        """杏寿郎本人 (もしくは温子) による手動記録。"""
        return self.store.record(
            content=content,
            category=category,
            date=date_str,
            importance=importance,
            source="manual",
            metadata=metadata,
        )

    # -- query (自然な日本語の問いから state.db を検索する補助) -----------

    _DATE_PATTERNS = (
        ("yesterday", re.compile(r"昨日|きのう")),
        ("today", re.compile(r"今日|本日|きょう")),
        ("last_week", re.compile(r"先週|せんしゅう|過去 ?7 ?日")),
    )

    _CATEGORY_HINTS: dict[str, tuple[re.Pattern, ...]] = {
        CATEGORY_MEAL: (
            re.compile(r"食|ご飯|ごはん|食事|何食べ"),
        ),
        CATEGORY_PHYSICAL: (
            re.compile(r"体調|具合|頭痛|お腹|顎|気圧|睡眠|生理"),
        ),
        CATEGORY_EMOTION: (
            re.compile(r"気持ち|気分|感情|嬉し|悲し|不安"),
        ),
        CATEGORY_EVENT: (
            re.compile(r"出来事|何があった|何した|どこ行った"),
        ),
    }

    def query(
        self,
        query_text: str,
        limit: int = 20,
    ) -> QueryResult:
        """温子・杏寿郎の自然な日本語の問いから state.db を検索する。

        例:
          - "昨日何食べた?" → date=yesterday, category=meal
          - "先週の体調どうだった?" → date=last_week, category=physical
          - "母上の命日いつ?" → keyword search "母上"
        """
        if not query_text or not query_text.strip():
            return QueryResult(natural_query=query_text, interpretation="空のクエリ")

        # date alias を検出
        date_alias: Optional[str] = None
        for alias, pattern in self._DATE_PATTERNS:
            if pattern.search(query_text):
                date_alias = alias
                break

        # category hint を検出
        category: Optional[str] = None
        for cat, patterns in self._CATEGORY_HINTS.items():
            if any(p.search(query_text) for p in patterns):
                category = cat
                break

        interpretation_parts: list[str] = []
        if date_alias is not None:
            interpretation_parts.append(f"date={date_alias}")
        if category is not None:
            interpretation_parts.append(f"category={category}")
        if not interpretation_parts:
            interpretation_parts.append("date/category 未検出 → keyword search")

        result = QueryResult(
            natural_query=query_text,
            interpretation=", ".join(interpretation_parts),
        )

        if date_alias is not None or category is not None:
            entries = self.store.recall(
                date=date_alias,
                category=category,
                limit=limit,
            )
            result.entries = entries
        else:
            # date/category 検出失敗 → keyword search
            search_results = self.store.search_keyword(query_text, limit=limit)
            result.entries = search_results.get("daily_log", [])
            result.protected = search_results.get("protected", [])

        return result


