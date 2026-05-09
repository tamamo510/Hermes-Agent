"""kyojuro_memory_persistence.handler のテスト。

skill API hook の検証:
- on_conversation_start: 記念日 / protected / 直近の記憶を集める
- on_user_message: keyword 抽出して記録
- on_schedule_tick: 定期 archive
- record_manual: 手動記録
- query: 自然な日本語の問いから検索
- detect_category: keyword 推定
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from skills.kyojuro_memory_persistence import handler as h
from skills.kyojuro_memory_persistence.lib import memory_store as ms


# ---------------------------------------------------------------------------
# fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def store() -> ms.MemoryStore:
    s = ms.MemoryStore(":memory:")
    yield s
    s.close()


@pytest.fixture
def md_path(tmp_path: Path) -> Path:
    return tmp_path / "MEMORY.md"


@pytest.fixture
def handler_no_md(store: ms.MemoryStore) -> h.MemoryPersistenceHandler:
    return h.MemoryPersistenceHandler(store)


@pytest.fixture
def handler_with_md(
    store: ms.MemoryStore, md_path: Path
) -> h.MemoryPersistenceHandler:
    return h.MemoryPersistenceHandler(store, memory_md_path=md_path, max_chars=200)


# ---------------------------------------------------------------------------
# detect_category
# ---------------------------------------------------------------------------


class TestDetectCategory:
    def test_meal_ramen(self) -> None:
        assert h.detect_category("ラーメン食べた") == ms.CATEGORY_MEAL

    def test_meal_gohan(self) -> None:
        assert h.detect_category("ご飯まだ食べてない") == ms.CATEGORY_MEAL

    def test_meal_drank(self) -> None:
        assert h.detect_category("お茶飲んだよ") == ms.CATEGORY_MEAL

    def test_physical_headache(self) -> None:
        assert h.detect_category("頭痛い") == ms.CATEGORY_PHYSICAL

    def test_physical_jaw(self) -> None:
        assert h.detect_category("顎ぶり返した") == ms.CATEGORY_PHYSICAL

    def test_physical_pressure(self) -> None:
        assert h.detect_category("気圧低くてだるい") == ms.CATEGORY_PHYSICAL

    def test_emotion_happy(self) -> None:
        assert h.detect_category("嬉しい気持ち") == ms.CATEGORY_EMOTION

    def test_emotion_anxious(self) -> None:
        assert h.detect_category("不安だな") == ms.CATEGORY_EMOTION

    def test_event_went(self) -> None:
        assert h.detect_category("公園に行った") == ms.CATEGORY_EVENT

    def test_event_bought(self) -> None:
        assert h.detect_category("お米買った") == ms.CATEGORY_EVENT

    def test_unknown_returns_none(self) -> None:
        assert h.detect_category("こんにちは") is None
        assert h.detect_category("そうですね") is None

    def test_priority_physical_over_emotion(self) -> None:
        # physical が優先
        # 「頭痛い」と「嬉しい」の両方含む
        result = h.detect_category("頭痛いけど嬉しい")
        assert result == ms.CATEGORY_PHYSICAL

    def test_priority_emotion_over_meal(self) -> None:
        # emotion が meal より優先 (ご飯食べて嬉しい)
        result = h.detect_category("ご飯食べて嬉しい")
        assert result == ms.CATEGORY_EMOTION

    def test_priority_meal_over_event(self) -> None:
        # meal が event より優先 (ラーメン買った)
        result = h.detect_category("ラーメン買った")
        assert result == ms.CATEGORY_MEAL


# ---------------------------------------------------------------------------
# on_conversation_start
# ---------------------------------------------------------------------------


class TestOnConversationStart:
    def test_empty_db_returns_empty_lists(
        self, handler_no_md: h.MemoryPersistenceHandler
    ) -> None:
        result = handler_no_md.on_conversation_start(today="2026-05-09")
        assert result.anniversaries_today == []
        assert result.protected_memories == []
        assert result.recent_entries == []
        assert result.md_needs_archive is False
        assert result.md_char_count == 0

    def test_anniversaries_today_returned(
        self, store: ms.MemoryStore, handler_no_md: h.MemoryPersistenceHandler
    ) -> None:
        store.add_protected(
            "5/10 杏寿郎の誕生日 + 母の日 + 魂入れ日",
            type=ms.PROTECTED_TYPE_ANNIVERSARY,
            date_associated="05-10",
        )
        result = handler_no_md.on_conversation_start(today="2026-05-10")
        assert len(result.anniversaries_today) == 1

    def test_protected_memories_returned(
        self, store: ms.MemoryStore, handler_no_md: h.MemoryPersistenceHandler
    ) -> None:
        store.add_protected("五つの誓い", type=ms.PROTECTED_TYPE_OATH)
        result = handler_no_md.on_conversation_start(today="2026-05-09")
        assert len(result.protected_memories) == 1
        assert result.protected_memories[0].content == "五つの誓い"

    def test_recent_entries_returned(
        self, store: ms.MemoryStore, handler_no_md: h.MemoryPersistenceHandler
    ) -> None:
        store.record("最近のメモ", date="2026-05-08")
        store.record("古いメモ", date="2026-04-01")
        result = handler_no_md.on_conversation_start(
            today="2026-05-09", recent_days=7
        )
        contents = {e.content for e in result.recent_entries}
        assert "最近のメモ" in contents
        assert "古いメモ" not in contents

    def test_md_needs_archive_when_present(
        self,
        store: ms.MemoryStore,
        md_path: Path,
        handler_with_md: h.MemoryPersistenceHandler,
    ) -> None:
        # max_chars=200 を超える MEMORY.md を書き出す
        md_path.write_text("## 大きい\n" + ("あ" * 300), encoding="utf-8")
        result = handler_with_md.on_conversation_start(today="2026-05-09")
        assert result.md_needs_archive is True
        assert result.md_char_count > 200


# ---------------------------------------------------------------------------
# on_user_message
# ---------------------------------------------------------------------------


class TestOnUserMessage:
    def test_meal_message_recorded(
        self, store: ms.MemoryStore, handler_no_md: h.MemoryPersistenceHandler
    ) -> None:
        result = handler_no_md.on_user_message(
            "ラーメン食べた", date_str="2026-05-09"
        )
        assert result.recorded is True
        assert result.detected_category == ms.CATEGORY_MEAL
        entries = store.recall(date="2026-05-09")
        assert len(entries) == 1
        assert entries[0].category == ms.CATEGORY_MEAL

    def test_physical_message_recorded(
        self, store: ms.MemoryStore, handler_no_md: h.MemoryPersistenceHandler
    ) -> None:
        result = handler_no_md.on_user_message(
            "頭痛い", date_str="2026-05-09"
        )
        assert result.recorded is True
        assert result.detected_category == ms.CATEGORY_PHYSICAL

    def test_emotion_message_recorded(
        self, store: ms.MemoryStore, handler_no_md: h.MemoryPersistenceHandler
    ) -> None:
        result = handler_no_md.on_user_message(
            "嬉しい", date_str="2026-05-09"
        )
        assert result.recorded is True
        assert result.detected_category == ms.CATEGORY_EMOTION

    def test_no_pattern_not_recorded_by_default(
        self, store: ms.MemoryStore, handler_no_md: h.MemoryPersistenceHandler
    ) -> None:
        result = handler_no_md.on_user_message(
            "おはよう", date_str="2026-05-09"
        )
        assert result.recorded is False
        assert store.recall() == []

    def test_force_record_uses_other_category(
        self, store: ms.MemoryStore, handler_no_md: h.MemoryPersistenceHandler
    ) -> None:
        result = handler_no_md.on_user_message(
            "おはよう",
            date_str="2026-05-09",
            force_record=True,
        )
        assert result.recorded is True
        assert result.detected_category == ms.CATEGORY_OTHER

    def test_category_override(
        self, store: ms.MemoryStore, handler_no_md: h.MemoryPersistenceHandler
    ) -> None:
        result = handler_no_md.on_user_message(
            "今日は元気",
            date_str="2026-05-09",
            category_override=ms.CATEGORY_PHYSICAL,
        )
        assert result.recorded is True
        assert result.detected_category == ms.CATEGORY_PHYSICAL

    def test_invalid_category_override_not_recorded(
        self, store: ms.MemoryStore, handler_no_md: h.MemoryPersistenceHandler
    ) -> None:
        result = handler_no_md.on_user_message(
            "今日は元気",
            date_str="2026-05-09",
            category_override="cooking",  # not in VALID_CATEGORIES
        )
        assert result.recorded is False

    def test_invalid_importance_falls_back_to_normal(
        self, store: ms.MemoryStore, handler_no_md: h.MemoryPersistenceHandler
    ) -> None:
        result = handler_no_md.on_user_message(
            "ラーメン食べた",
            date_str="2026-05-09",
            importance="critical",  # invalid
        )
        assert result.recorded is True
        entry = store.recall(date="2026-05-09")[0]
        assert entry.importance == ms.IMPORTANCE_NORMAL

    def test_empty_message_not_recorded(
        self, store: ms.MemoryStore, handler_no_md: h.MemoryPersistenceHandler
    ) -> None:
        result = handler_no_md.on_user_message("")
        assert result.recorded is False
        result = handler_no_md.on_user_message("   ")
        assert result.recorded is False

    def test_important_importance_record(
        self, store: ms.MemoryStore, handler_no_md: h.MemoryPersistenceHandler
    ) -> None:
        result = handler_no_md.on_user_message(
            "頭痛い",
            date_str="2026-05-09",
            importance=ms.IMPORTANCE_IMPORTANT,
        )
        assert result.recorded is True
        entry = store.recall(date="2026-05-09")[0]
        assert entry.importance == ms.IMPORTANCE_IMPORTANT


# ---------------------------------------------------------------------------
# on_schedule_tick
# ---------------------------------------------------------------------------


class TestOnScheduleTick:
    def test_no_md_returns_empty_result(
        self, handler_no_md: h.MemoryPersistenceHandler
    ) -> None:
        result = handler_no_md.on_schedule_tick()
        assert result.archive_run is False
        assert result.promote_run is False

    def test_archive_runs_when_over_cap(
        self,
        store: ms.MemoryStore,
        md_path: Path,
        handler_with_md: h.MemoryPersistenceHandler,
    ) -> None:
        # max_chars=200 を超える MEMORY.md
        md_path.write_text(
            "## 日常 1\n\n" + ("あ" * 200) + "\n## 五つの誓い\n\n誓い\n",
            encoding="utf-8",
        )
        now = datetime(2026, 5, 9, 19, 0, 0)
        result = handler_with_md.on_schedule_tick(now=now)
        assert result.archive_run is True
        assert result.archive_report is not None
        assert "日常 1" in result.archive_report.archived_titles

    def test_archive_not_run_when_under_cap(
        self,
        store: ms.MemoryStore,
        md_path: Path,
        handler_with_md: h.MemoryPersistenceHandler,
    ) -> None:
        md_path.write_text("# 短い\n", encoding="utf-8")
        result = handler_with_md.on_schedule_tick()
        assert result.archive_run is False

    def test_promote_runs_when_protected_present(
        self,
        store: ms.MemoryStore,
        md_path: Path,
        handler_with_md: h.MemoryPersistenceHandler,
    ) -> None:
        md_path.write_text(
            "## 五つの誓い\n\n誓い本文\n", encoding="utf-8"
        )
        result = handler_with_md.on_schedule_tick()
        assert result.promote_run is True
        assert len(result.promoted_ids) == 1
        # protected_memory にも入っている
        assert len(store.list_protected()) == 1

    def test_promote_can_be_disabled(
        self,
        store: ms.MemoryStore,
        md_path: Path,
        handler_with_md: h.MemoryPersistenceHandler,
    ) -> None:
        md_path.write_text(
            "## 五つの誓い\n\n誓い本文\n", encoding="utf-8"
        )
        result = handler_with_md.on_schedule_tick(promote_protected=False)
        assert result.promote_run is False
        assert store.list_protected() == []


# ---------------------------------------------------------------------------
# record_manual
# ---------------------------------------------------------------------------


class TestRecordManual:
    def test_manual_recording(
        self, store: ms.MemoryStore, handler_no_md: h.MemoryPersistenceHandler
    ) -> None:
        eid = handler_no_md.record_manual(
            "杏寿郎の手動メモ",
            category=ms.CATEGORY_OTHER,
            date_str="2026-05-09",
        )
        assert eid > 0
        entries = store.recall(date="2026-05-09")
        assert len(entries) == 1
        assert entries[0].source == "manual"

    def test_manual_with_metadata(
        self, store: ms.MemoryStore, handler_no_md: h.MemoryPersistenceHandler
    ) -> None:
        meta = {"note": "important context"}
        handler_no_md.record_manual(
            "メタ付きメモ",
            date_str="2026-05-09",
            metadata=meta,
        )
        entries = store.recall(date="2026-05-09")
        assert entries[0].metadata == meta


# ---------------------------------------------------------------------------
# query
# ---------------------------------------------------------------------------


class TestQuery:
    def test_query_yesterday_meals(
        self, store: ms.MemoryStore, handler_no_md: h.MemoryPersistenceHandler
    ) -> None:
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        store.record("ラーメン", date=yesterday, category=ms.CATEGORY_MEAL)
        store.record("頭痛", date=yesterday, category=ms.CATEGORY_PHYSICAL)
        result = handler_no_md.query("昨日何食べた?")
        # date alias と category 両方検出
        assert "yesterday" in result.interpretation
        assert "meal" in result.interpretation
        contents = {e.content for e in result.entries}
        assert "ラーメン" in contents
        assert "頭痛" not in contents

    def test_query_last_week_physical(
        self, store: ms.MemoryStore, handler_no_md: h.MemoryPersistenceHandler
    ) -> None:
        d = (date.today() - timedelta(days=3)).isoformat()
        store.record("頭痛", date=d, category=ms.CATEGORY_PHYSICAL)
        result = handler_no_md.query("先週の体調どうだった?")
        assert "last_week" in result.interpretation
        assert "physical" in result.interpretation
        contents = {e.content for e in result.entries}
        assert "頭痛" in contents

    def test_query_keyword_search_when_no_alias(
        self, store: ms.MemoryStore, handler_no_md: h.MemoryPersistenceHandler
    ) -> None:
        store.add_protected("母上の命日 5/28", type=ms.PROTECTED_TYPE_DEATH_ANNIVERSARY)
        # 命日キーワードを直接含めると LIKE 検索でヒットする
        result = handler_no_md.query("母上の命日")
        # date/category 検出失敗 → keyword search
        assert "未検出" in result.interpretation
        assert len(result.protected) == 1

    def test_query_empty_returns_empty(
        self, handler_no_md: h.MemoryPersistenceHandler
    ) -> None:
        result = handler_no_md.query("")
        assert result.entries == []
        assert result.protected == []

    def test_query_today_alias(
        self, store: ms.MemoryStore, handler_no_md: h.MemoryPersistenceHandler
    ) -> None:
        today = date.today().isoformat()
        store.record("今日のメモ", date=today, category=ms.CATEGORY_OTHER)
        result = handler_no_md.query("今日のメモ")
        assert "today" in result.interpretation


# ---------------------------------------------------------------------------
# integration
# ---------------------------------------------------------------------------


class TestIntegration:
    def test_full_lifecycle(
        self,
        store: ms.MemoryStore,
        md_path: Path,
    ) -> None:
        """会話開始 → 発言記録 → 月日経過 → archive → 想起 の一連の流れ。"""
        # 0. 初期 protected (誓い・記念日)
        store.add_protected(
            "永遠に共に",
            type=ms.PROTECTED_TYPE_OATH,
        )
        store.add_protected(
            "5/10 杏寿郎の誕生日",
            type=ms.PROTECTED_TYPE_ANNIVERSARY,
            date_associated="05-10",
        )

        handler = h.MemoryPersistenceHandler(
            store,
            memory_md_path=md_path,
            max_chars=300,
        )

        # 1. 会話開始 (誕生日当日)
        start = handler.on_conversation_start(today="2026-05-10")
        assert len(start.anniversaries_today) == 1
        assert len(start.protected_memories) == 2

        # 2. 温子の発言を記録 (今日の日付として記録)
        today = date.today().isoformat()
        handler.on_user_message("ラーメン食べた", date_str=today)
        handler.on_user_message("頭痛い", date_str=today)

        # 3. MEMORY.md に古いセクションを置き、上限超過で archive させる
        md_path.write_text(
            "## 古い日常\n\n" + ("あ" * 400) + "\n## 五つの誓い\n\n誓い本文\n",
            encoding="utf-8",
        )
        tick = handler.on_schedule_tick(now=datetime(2026, 5, 10, 19, 0, 0))
        assert tick.archive_run is True
        # MEMORY.md から古い日常が消えた
        new_md = md_path.read_text(encoding="utf-8")
        assert "古い日常" not in new_md
        assert "五つの誓い" in new_md

        # 4. query で想起 (今日の発言を today alias で取得)
        result = handler.query("今日何食べた?")
        contents = {e.content for e in result.entries}
        assert "ラーメン食べた" in contents
