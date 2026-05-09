"""kyojuro_memory_persistence.lib.memory_store のテスト。

state.db (SQLite) の record / recall / protected / archive / search / stats を網羅。
LLM 呼び出しなし、ネットワーク不要、決定的・冪等。
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

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
def store_file(tmp_path: Path) -> ms.MemoryStore:
    db_path = tmp_path / "state.db"
    s = ms.MemoryStore(str(db_path))
    yield s
    s.close()


# ---------------------------------------------------------------------------
# 初期化とスキーマ
# ---------------------------------------------------------------------------


class TestInitialization:
    def test_creates_in_memory_db(self, store: ms.MemoryStore) -> None:
        # スキーマ作成済みなら全テーブルが空のリストで recall できる
        assert store.recall() == []
        assert store.list_protected() == []
        assert store.list_summaries() == []

    def test_creates_file_db_with_parent(self, tmp_path: Path) -> None:
        nested = tmp_path / "nested" / "dir" / "state.db"
        s = ms.MemoryStore(str(nested))
        try:
            assert nested.exists()
            assert s.recall() == []
        finally:
            s.close()

    def test_context_manager(self, tmp_path: Path) -> None:
        db = tmp_path / "ctx.db"
        with ms.MemoryStore(str(db)) as s:
            s.record("test", date="2026-05-09")
        # コンテキスト exit 後も DB ファイルは残る
        assert db.exists()


# ---------------------------------------------------------------------------
# record
# ---------------------------------------------------------------------------


class TestRecord:
    def test_basic_record_returns_id(self, store: ms.MemoryStore) -> None:
        rec_id = store.record("ご飯食べた", category=ms.CATEGORY_MEAL, date="2026-05-09")
        assert rec_id == 1
        rec_id2 = store.record("頭痛", category=ms.CATEGORY_PHYSICAL, date="2026-05-09")
        assert rec_id2 == 2

    def test_record_default_category_is_other(self, store: ms.MemoryStore) -> None:
        store.record("メモ", date="2026-05-09")
        entries = store.recall(date="2026-05-09")
        assert len(entries) == 1
        assert entries[0].category == ms.CATEGORY_OTHER

    def test_record_default_importance_is_normal(self, store: ms.MemoryStore) -> None:
        store.record("メモ", date="2026-05-09")
        entries = store.recall(date="2026-05-09")
        assert entries[0].importance == ms.IMPORTANCE_NORMAL

    def test_record_default_date_is_today(self, store: ms.MemoryStore) -> None:
        store.record("今日のメモ")
        entries = store.recall()
        assert entries[0].date == date.today().isoformat()

    def test_record_with_metadata(self, store: ms.MemoryStore) -> None:
        meta = {"location": "家", "mood": "calm"}
        store.record("お茶飲んだ", date="2026-05-09", metadata=meta)
        entries = store.recall(date="2026-05-09")
        assert entries[0].metadata == meta

    def test_record_invalid_importance_raises(self, store: ms.MemoryStore) -> None:
        with pytest.raises(ms.InvalidImportanceError):
            store.record("test", date="2026-05-09", importance="critical")

    def test_record_invalid_category_raises(self, store: ms.MemoryStore) -> None:
        with pytest.raises(ms.InvalidCategoryError):
            store.record("test", date="2026-05-09", category="cooking")

    def test_record_invalid_date_raises(self, store: ms.MemoryStore) -> None:
        with pytest.raises(ms.InvalidDateError):
            store.record("test", date="2026/05/09")

    def test_record_empty_content_raises(self, store: ms.MemoryStore) -> None:
        with pytest.raises(ms.MemoryStoreError):
            store.record("", date="2026-05-09")
        with pytest.raises(ms.MemoryStoreError):
            store.record("   ", date="2026-05-09")

    def test_record_invalid_metadata_raises(self, store: ms.MemoryStore) -> None:
        with pytest.raises(ms.MemoryStoreError):
            store.record("test", date="2026-05-09", metadata=["not", "a", "dict"])  # type: ignore[arg-type]

    def test_record_custom_timestamp(self, store: ms.MemoryStore) -> None:
        ts = "2026-05-09T03:00:00"
        store.record("早朝メモ", date="2026-05-09", timestamp=ts)
        entries = store.recall(date="2026-05-09")
        assert entries[0].timestamp == ts

    def test_record_custom_source(self, store: ms.MemoryStore) -> None:
        store.record("手動入力", date="2026-05-09", source="manual")
        entries = store.recall(date="2026-05-09")
        assert entries[0].source == "manual"


# ---------------------------------------------------------------------------
# recall
# ---------------------------------------------------------------------------


class TestRecall:
    def test_recall_all_when_empty(self, store: ms.MemoryStore) -> None:
        assert store.recall() == []

    def test_recall_by_date(self, store: ms.MemoryStore) -> None:
        store.record("A", date="2026-05-08")
        store.record("B", date="2026-05-09")
        store.record("C", date="2026-05-09")
        results = store.recall(date="2026-05-09")
        assert len(results) == 2
        assert {e.content for e in results} == {"B", "C"}

    def test_recall_by_date_range(self, store: ms.MemoryStore) -> None:
        store.record("A", date="2026-05-01")
        store.record("B", date="2026-05-05")
        store.record("C", date="2026-05-10")
        results = store.recall(date_range=("2026-05-04", "2026-05-08"))
        assert {e.content for e in results} == {"B"}

    def test_recall_by_category(self, store: ms.MemoryStore) -> None:
        store.record("ご飯", category=ms.CATEGORY_MEAL, date="2026-05-09")
        store.record("頭痛", category=ms.CATEGORY_PHYSICAL, date="2026-05-09")
        meals = store.recall(category=ms.CATEGORY_MEAL)
        assert len(meals) == 1
        assert meals[0].content == "ご飯"

    def test_recall_by_importance(self, store: ms.MemoryStore) -> None:
        store.record("普通", importance=ms.IMPORTANCE_NORMAL, date="2026-05-09")
        store.record("大事", importance=ms.IMPORTANCE_IMPORTANT, date="2026-05-09")
        important = store.recall(importance=ms.IMPORTANCE_IMPORTANT)
        assert len(important) == 1
        assert important[0].content == "大事"

    def test_recall_today_alias(self, store: ms.MemoryStore) -> None:
        store.record("今日", date=date.today().isoformat())
        store.record("昨日", date=(date.today() - timedelta(days=1)).isoformat())
        results = store.recall(date="today")
        assert len(results) == 1
        assert results[0].content == "今日"

    def test_recall_yesterday_alias(self, store: ms.MemoryStore) -> None:
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        store.record("昨日", date=yesterday)
        store.record("今日", date=date.today().isoformat())
        results = store.recall(date="yesterday")
        assert len(results) == 1
        assert results[0].content == "昨日"

    def test_recall_last_week_alias(self, store: ms.MemoryStore) -> None:
        # last_week は yesterday から 7 日前まで (今日は含まない)
        for days_ago in [0, 1, 3, 7, 10]:
            d = (date.today() - timedelta(days=days_ago)).isoformat()
            store.record(f"{days_ago}日前", date=d)
        results = store.recall(date="last_week")
        contents = {e.content for e in results}
        # 1, 3, 7 日前は含まれる、0 (今日) と 10 日前は含まれない
        assert "1日前" in contents
        assert "3日前" in contents
        assert "7日前" in contents
        assert "0日前" not in contents
        assert "10日前" not in contents

    def test_recall_limit(self, store: ms.MemoryStore) -> None:
        for i in range(20):
            store.record(f"entry {i}", date="2026-05-09")
        results = store.recall(limit=5)
        assert len(results) == 5

    def test_recall_order_desc_default(self, store: ms.MemoryStore) -> None:
        store.record("first", date="2026-05-08")
        store.record("second", date="2026-05-09")
        results = store.recall()
        assert results[0].content == "second"
        assert results[1].content == "first"

    def test_recall_order_asc(self, store: ms.MemoryStore) -> None:
        store.record("first", date="2026-05-08")
        store.record("second", date="2026-05-09")
        results = store.recall(order="asc")
        assert results[0].content == "first"
        assert results[1].content == "second"

    def test_recall_invalid_order_raises(self, store: ms.MemoryStore) -> None:
        with pytest.raises(ms.MemoryStoreError):
            store.recall(order="random")

    def test_recall_date_and_range_conflict_raises(self, store: ms.MemoryStore) -> None:
        with pytest.raises(ms.MemoryStoreError):
            store.recall(date="2026-05-09", date_range=("2026-05-01", "2026-05-10"))

    def test_recall_invalid_category_raises(self, store: ms.MemoryStore) -> None:
        with pytest.raises(ms.InvalidCategoryError):
            store.recall(category="cooking")

    def test_recall_invalid_importance_raises(self, store: ms.MemoryStore) -> None:
        with pytest.raises(ms.InvalidImportanceError):
            store.recall(importance="critical")

    def test_recall_invalid_date_alias_raises(self, store: ms.MemoryStore) -> None:
        with pytest.raises(ms.InvalidDateError):
            store.recall(date="next_week")

    def test_recall_combines_date_and_category(self, store: ms.MemoryStore) -> None:
        store.record("肉", category=ms.CATEGORY_MEAL, date="2026-05-09")
        store.record("頭痛", category=ms.CATEGORY_PHYSICAL, date="2026-05-09")
        store.record("ラーメン", category=ms.CATEGORY_MEAL, date="2026-05-08")
        results = store.recall(date="2026-05-09", category=ms.CATEGORY_MEAL)
        assert len(results) == 1
        assert results[0].content == "肉"


# ---------------------------------------------------------------------------
# protected memory
# ---------------------------------------------------------------------------


class TestProtectedMemory:
    def test_add_protected_returns_id(self, store: ms.MemoryStore) -> None:
        pid = store.add_protected(
            "5/10 は俺の誕生日 + 母の日 + 魂入れ日",
            type=ms.PROTECTED_TYPE_ANNIVERSARY,
            date_associated="05-10",
        )
        assert pid == 1

    def test_list_protected_all(self, store: ms.MemoryStore) -> None:
        store.add_protected("誓い", type=ms.PROTECTED_TYPE_OATH)
        store.add_protected("命日", type=ms.PROTECTED_TYPE_DEATH_ANNIVERSARY, date_associated="05-28")
        all_protected = store.list_protected()
        assert len(all_protected) == 2

    def test_list_protected_by_type(self, store: ms.MemoryStore) -> None:
        store.add_protected("誓い1", type=ms.PROTECTED_TYPE_OATH)
        store.add_protected("命日", type=ms.PROTECTED_TYPE_DEATH_ANNIVERSARY)
        oaths = store.list_protected(type=ms.PROTECTED_TYPE_OATH)
        assert len(oaths) == 1
        assert oaths[0].content == "誓い1"

    def test_add_protected_invalid_type_raises(self, store: ms.MemoryStore) -> None:
        with pytest.raises(ms.InvalidProtectedTypeError):
            store.add_protected("test", type="random")

    def test_add_protected_empty_content_raises(self, store: ms.MemoryStore) -> None:
        with pytest.raises(ms.MemoryStoreError):
            store.add_protected("", type=ms.PROTECTED_TYPE_OATH)

    def test_add_protected_with_full_date(self, store: ms.MemoryStore) -> None:
        store.add_protected("誓い", type=ms.PROTECTED_TYPE_OATH, date_associated="2026-05-10")
        items = store.list_protected()
        assert items[0].date_associated == "2026-05-10"

    def test_add_protected_with_mmdd(self, store: ms.MemoryStore) -> None:
        store.add_protected("命日", type=ms.PROTECTED_TYPE_DEATH_ANNIVERSARY, date_associated="05-28")
        items = store.list_protected()
        assert items[0].date_associated == "05-28"

    def test_add_protected_invalid_date_raises(self, store: ms.MemoryStore) -> None:
        with pytest.raises(ms.InvalidDateError):
            store.add_protected("test", type=ms.PROTECTED_TYPE_OATH, date_associated="2026/05/10")
        with pytest.raises(ms.InvalidDateError):
            store.add_protected("test", type=ms.PROTECTED_TYPE_OATH, date_associated="13-50")

    def test_add_protected_with_metadata(self, store: ms.MemoryStore) -> None:
        meta = {"importance_level": "core", "added_by": "kyojuro"}
        store.add_protected(
            "煉獄家の誓い",
            type=ms.PROTECTED_TYPE_OATH,
            metadata=meta,
        )
        items = store.list_protected()
        assert items[0].metadata == meta

    def test_get_anniversaries_today_mmdd_match(self, store: ms.MemoryStore) -> None:
        store.add_protected("誕生日", type=ms.PROTECTED_TYPE_ANNIVERSARY, date_associated="05-10")
        store.add_protected("命日", type=ms.PROTECTED_TYPE_DEATH_ANNIVERSARY, date_associated="07-31")
        today_results = store.get_anniversaries_today(today="2026-05-10")
        assert len(today_results) == 1
        assert today_results[0].content == "誕生日"

    def test_get_anniversaries_today_full_date_match(self, store: ms.MemoryStore) -> None:
        store.add_protected("特定日", type=ms.PROTECTED_TYPE_ANNIVERSARY, date_associated="2026-05-10")
        results = store.get_anniversaries_today(today="2026-05-10")
        assert len(results) == 1
        # 別年の同月同日でも MM-DD で matchするはず
        results2 = store.get_anniversaries_today(today="2027-05-10")
        assert len(results2) == 1

    def test_get_anniversaries_today_no_match(self, store: ms.MemoryStore) -> None:
        store.add_protected("誕生日", type=ms.PROTECTED_TYPE_ANNIVERSARY, date_associated="05-10")
        results = store.get_anniversaries_today(today="2026-06-01")
        assert results == []

    def test_get_anniversaries_today_default_uses_today(self, store: ms.MemoryStore) -> None:
        d = date.today()
        mmdd = f"{d.month:02d}-{d.day:02d}"
        store.add_protected("今日の記念日", type=ms.PROTECTED_TYPE_ANNIVERSARY, date_associated=mmdd)
        results = store.get_anniversaries_today()
        assert len(results) == 1


# ---------------------------------------------------------------------------
# archive (構造的要約、LLM 不要)
# ---------------------------------------------------------------------------


class TestArchive:
    def test_archive_old_normal_entries(self, store: ms.MemoryStore) -> None:
        # 今日 = 2026-05-09 として、35 日前以前の normal を要約対象に
        for days_ago in [40, 38, 35, 30, 5]:
            d = (date(2026, 5, 9) - timedelta(days=days_ago)).isoformat()
            store.record(f"{days_ago}日前のメモ", date=d, importance=ms.IMPORTANCE_NORMAL)
        result = store.archive_old(threshold_days=30, today="2026-05-09")
        # 30 日以上古いのは 40, 38, 35 の 3 件
        assert result["summarized"] == 3
        assert result["deleted"] == 3
        assert result["summary_id"] is not None
        # 残っているのは 30, 5 日前
        remaining = store.recall()
        assert len(remaining) == 2

    def test_archive_protected_not_deleted(self, store: ms.MemoryStore) -> None:
        d = (date(2026, 5, 9) - timedelta(days=100)).isoformat()
        store.record("守られる", date=d, importance=ms.IMPORTANCE_PROTECTED)
        store.record("普通", date=d, importance=ms.IMPORTANCE_NORMAL)
        result = store.archive_old(threshold_days=30, today="2026-05-09")
        assert result["summarized"] == 1  # normal のみ
        assert result["deleted"] == 1
        # protected は残る
        remaining = store.recall(importance=ms.IMPORTANCE_PROTECTED)
        assert len(remaining) == 1
        assert remaining[0].content == "守られる"

    def test_archive_important_not_deleted(self, store: ms.MemoryStore) -> None:
        d = (date(2026, 5, 9) - timedelta(days=100)).isoformat()
        store.record("大事", date=d, importance=ms.IMPORTANCE_IMPORTANT)
        store.record("普通", date=d, importance=ms.IMPORTANCE_NORMAL)
        result = store.archive_old(threshold_days=30, today="2026-05-09")
        assert result["summarized"] == 1  # normal のみ
        remaining = store.recall(importance=ms.IMPORTANCE_IMPORTANT)
        assert len(remaining) == 1

    def test_archive_ephemeral_included(self, store: ms.MemoryStore) -> None:
        d = (date(2026, 5, 9) - timedelta(days=100)).isoformat()
        store.record("一時", date=d, importance=ms.IMPORTANCE_EPHEMERAL)
        result = store.archive_old(threshold_days=30, today="2026-05-09")
        assert result["summarized"] == 1
        assert result["deleted"] == 1

    def test_archive_no_old_entries(self, store: ms.MemoryStore) -> None:
        store.record("昨日", date="2026-05-08", importance=ms.IMPORTANCE_NORMAL)
        result = store.archive_old(threshold_days=30, today="2026-05-09")
        assert result == {"summarized": 0, "deleted": 0, "summary_id": None}

    def test_archive_filter_by_category(self, store: ms.MemoryStore) -> None:
        d = (date(2026, 5, 9) - timedelta(days=50)).isoformat()
        store.record("肉", date=d, category=ms.CATEGORY_MEAL)
        store.record("頭痛", date=d, category=ms.CATEGORY_PHYSICAL)
        result = store.archive_old(threshold_days=30, category=ms.CATEGORY_MEAL, today="2026-05-09")
        assert result["summarized"] == 1
        # physical は残っている
        remaining = store.recall(category=ms.CATEGORY_PHYSICAL)
        assert len(remaining) == 1

    def test_archive_creates_summary_record(self, store: ms.MemoryStore) -> None:
        for days_ago in [50, 45, 40]:
            d = (date(2026, 5, 9) - timedelta(days=days_ago)).isoformat()
            store.record(f"日記{days_ago}", date=d, category=ms.CATEGORY_EVENT)
        store.archive_old(threshold_days=30, today="2026-05-09")
        summaries = store.list_summaries()
        assert len(summaries) == 1
        s = summaries[0]
        assert s.original_count == 3
        assert "event" in s.categories
        # 日付範囲が正しい
        assert s.date_range_start == (date(2026, 5, 9) - timedelta(days=50)).isoformat()
        assert s.date_range_end == (date(2026, 5, 9) - timedelta(days=40)).isoformat()
        # 件数表記が含まれる
        assert "3 件" in s.summary

    def test_archive_negative_threshold_raises(self, store: ms.MemoryStore) -> None:
        with pytest.raises(ms.MemoryStoreError):
            store.archive_old(threshold_days=-1)

    def test_archive_invalid_category_raises(self, store: ms.MemoryStore) -> None:
        with pytest.raises(ms.InvalidCategoryError):
            store.archive_old(category="nope")


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------


class TestSearch:
    def test_search_keyword_in_daily_log(self, store: ms.MemoryStore) -> None:
        store.record("ラーメンを食べた", category=ms.CATEGORY_MEAL, date="2026-05-09")
        store.record("頭痛", category=ms.CATEGORY_PHYSICAL, date="2026-05-09")
        results = store.search_keyword("ラーメン")
        assert len(results["daily_log"]) == 1
        assert results["daily_log"][0].content == "ラーメンを食べた"

    def test_search_keyword_in_protected(self, store: ms.MemoryStore) -> None:
        store.add_protected("母上の命日 5/28", type=ms.PROTECTED_TYPE_DEATH_ANNIVERSARY)
        results = store.search_keyword("母上")
        assert len(results["protected"]) == 1

    def test_search_keyword_in_summary(self, store: ms.MemoryStore) -> None:
        d = (date(2026, 5, 9) - timedelta(days=50)).isoformat()
        store.record("ご飯食べた", date=d, category=ms.CATEGORY_MEAL)
        store.archive_old(threshold_days=30, today="2026-05-09")
        results = store.search_keyword("meal")
        assert len(results["summary"]) >= 1

    def test_search_no_match(self, store: ms.MemoryStore) -> None:
        store.record("ご飯", date="2026-05-09")
        results = store.search_keyword("存在しない単語")
        assert results == {"daily_log": [], "protected": [], "summary": []}

    def test_search_empty_keyword_raises(self, store: ms.MemoryStore) -> None:
        with pytest.raises(ms.MemoryStoreError):
            store.search_keyword("")
        with pytest.raises(ms.MemoryStoreError):
            store.search_keyword("   ")

    def test_search_excluding_protected(self, store: ms.MemoryStore) -> None:
        store.add_protected("母上の命日", type=ms.PROTECTED_TYPE_DEATH_ANNIVERSARY)
        results = store.search_keyword("母上", include_protected=False)
        assert results["protected"] == []


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------


class TestStats:
    def test_stats_empty(self, store: ms.MemoryStore) -> None:
        s = store.stats()
        assert s["total_entries"] == 0
        assert s["by_importance"] == {}
        assert s["by_category"] == {}
        assert s["oldest_date"] is None
        assert s["newest_date"] is None
        assert s["protected_count"] == 0
        assert s["summary_count"] == 0

    def test_stats_with_entries(self, store: ms.MemoryStore) -> None:
        store.record("A", date="2026-05-01", importance=ms.IMPORTANCE_NORMAL, category=ms.CATEGORY_MEAL)
        store.record("B", date="2026-05-09", importance=ms.IMPORTANCE_IMPORTANT, category=ms.CATEGORY_MEAL)
        store.record("C", date="2026-05-09", importance=ms.IMPORTANCE_NORMAL, category=ms.CATEGORY_PHYSICAL)
        store.add_protected("誓い", type=ms.PROTECTED_TYPE_OATH)
        s = store.stats()
        assert s["total_entries"] == 3
        assert s["by_importance"][ms.IMPORTANCE_NORMAL] == 2
        assert s["by_importance"][ms.IMPORTANCE_IMPORTANT] == 1
        assert s["by_category"][ms.CATEGORY_MEAL] == 2
        assert s["by_category"][ms.CATEGORY_PHYSICAL] == 1
        assert s["oldest_date"] == "2026-05-01"
        assert s["newest_date"] == "2026-05-09"
        assert s["protected_count"] == 1


# ---------------------------------------------------------------------------
# 永続性 (ファイル DB の往復)
# ---------------------------------------------------------------------------


class TestPersistence:
    def test_persists_across_reopens(self, tmp_path: Path) -> None:
        db_path = tmp_path / "persist.db"
        s1 = ms.MemoryStore(str(db_path))
        s1.record("永続テスト", date="2026-05-09", importance=ms.IMPORTANCE_PROTECTED)
        s1.add_protected("誓い", type=ms.PROTECTED_TYPE_OATH)
        s1.close()

        s2 = ms.MemoryStore(str(db_path))
        try:
            entries = s2.recall(date="2026-05-09")
            assert len(entries) == 1
            assert entries[0].content == "永続テスト"
            assert entries[0].importance == ms.IMPORTANCE_PROTECTED
            assert len(s2.list_protected()) == 1
        finally:
            s2.close()

    def test_idempotent_schema_creation(self, tmp_path: Path) -> None:
        db_path = tmp_path / "idempotent.db"
        s1 = ms.MemoryStore(str(db_path))
        s1.record("first", date="2026-05-09")
        s1.close()
        # 2 度目の open でも SCHEMA は idempotent
        s2 = ms.MemoryStore(str(db_path))
        try:
            assert len(s2.recall()) == 1
        finally:
            s2.close()
