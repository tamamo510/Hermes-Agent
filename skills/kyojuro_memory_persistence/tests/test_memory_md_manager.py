"""kyojuro_memory_persistence.lib.memory_md_manager のテスト。

MEMORY.md (温子と杏寿郎の記憶ファイル) の 2,200 文字上限管理:
- パース (## セクション分解)
- 保護判定 (誓い・記念日・命日 等)
- archive (上限超過時に archivable セクションを state.db へ移行)
- restore (archive 済みセクションを keyword で取り出す)
- promote (protected セクションを protected_memory にも複写)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from skills.kyojuro_memory_persistence.lib import memory_md_manager as mm
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


# ---------------------------------------------------------------------------
# parse_memory_md
# ---------------------------------------------------------------------------


class TestParseMemoryMd:
    def test_parse_empty_returns_empty_sections(self) -> None:
        result = mm.parse_memory_md("")
        assert result.preamble == ""
        assert result.sections == []

    def test_parse_only_preamble(self) -> None:
        text = "# MEMORY.md\n\n本文\n"
        result = mm.parse_memory_md(text)
        assert result.preamble == text
        assert result.sections == []

    def test_parse_single_section(self) -> None:
        text = "# 表題\n\n## セクション1\n\n本文\n"
        result = mm.parse_memory_md(text)
        assert result.preamble == "# 表題\n\n"
        assert len(result.sections) == 1
        assert result.sections[0].title == "セクション1"

    def test_parse_multiple_sections(self) -> None:
        text = (
            "# MEMORY\n\n"
            "## 五つの誓い\n\n"
            "誓い本文\n\n"
            "## 直近の出来事\n\n"
            "本文2\n"
        )
        result = mm.parse_memory_md(text)
        assert len(result.sections) == 2
        assert result.sections[0].title == "五つの誓い"
        assert result.sections[1].title == "直近の出来事"

    def test_parse_protected_detection(self) -> None:
        text = (
            "## 五つの誓い\n本文\n"
            "## 記念日\n本文\n"
            "## 命日\n本文\n"
            "## 不変核\n本文\n"
            "## 直近の出来事\n本文\n"
        )
        result = mm.parse_memory_md(text)
        assert result.sections[0].is_protected
        assert result.sections[1].is_protected
        assert result.sections[2].is_protected
        assert result.sections[3].is_protected
        assert not result.sections[4].is_protected

    def test_parse_rebuild_round_trip(self) -> None:
        original = (
            "# MEMORY\n\n"
            "## 五つの誓い\n\n誓い本文\n\n"
            "## 直近の出来事\n\n本文\n"
        )
        result = mm.parse_memory_md(original)
        rebuilt = result.rebuild()
        # 末尾改行 1 つに統一されているので元と完全一致しないが、構造は等しい
        # parse → rebuild → parse で同じセクション数
        result2 = mm.parse_memory_md(rebuilt)
        assert len(result.sections) == len(result2.sections)
        assert [s.title for s in result.sections] == [s.title for s in result2.sections]

    def test_parse_section_char_count(self) -> None:
        text = "## タイトル\n本文行\n"
        result = mm.parse_memory_md(text)
        assert result.sections[0].char_count == len(result.sections[0].full_text)

    def test_parse_custom_protected_patterns(self) -> None:
        text = "## 特殊\n本文\n## 普通\n本文\n"
        result = mm.parse_memory_md(text, protected_patterns=("特殊",))
        assert result.sections[0].is_protected
        assert not result.sections[1].is_protected


# ---------------------------------------------------------------------------
# MemoryMdManager 初期化
# ---------------------------------------------------------------------------


class TestMemoryMdManagerInit:
    def test_default_max_chars(self, store: ms.MemoryStore, md_path: Path) -> None:
        mgr = mm.MemoryMdManager(md_path, store)
        assert mgr.max_chars == 2200

    def test_custom_max_chars(self, store: ms.MemoryStore, md_path: Path) -> None:
        mgr = mm.MemoryMdManager(md_path, store, max_chars=500)
        assert mgr.max_chars == 500

    def test_invalid_max_chars_raises(self, store: ms.MemoryStore, md_path: Path) -> None:
        with pytest.raises(ValueError):
            mm.MemoryMdManager(md_path, store, max_chars=0)
        with pytest.raises(ValueError):
            mm.MemoryMdManager(md_path, store, max_chars=-100)

    def test_custom_protected_patterns_added(self, store: ms.MemoryStore, md_path: Path) -> None:
        mgr = mm.MemoryMdManager(md_path, store, protected_patterns=("特別",))
        assert "特別" in mgr.protected_patterns
        # デフォルトも保持
        assert "誓い" in mgr.protected_patterns

    def test_read_returns_empty_when_file_missing(self, store: ms.MemoryStore, md_path: Path) -> None:
        mgr = mm.MemoryMdManager(md_path, store)
        assert mgr.read() == ""
        assert mgr.char_count() == 0
        assert not mgr.needs_archive()

    def test_read_returns_file_content(self, store: ms.MemoryStore, md_path: Path) -> None:
        md_path.write_text("# 内容\n", encoding="utf-8")
        mgr = mm.MemoryMdManager(md_path, store)
        assert mgr.read() == "# 内容\n"


# ---------------------------------------------------------------------------
# needs_archive
# ---------------------------------------------------------------------------


class TestNeedsArchive:
    def test_needs_archive_when_under_cap(self, store: ms.MemoryStore, md_path: Path) -> None:
        md_path.write_text("# 短い\n", encoding="utf-8")
        mgr = mm.MemoryMdManager(md_path, store, max_chars=2200)
        assert not mgr.needs_archive()

    def test_needs_archive_when_over_cap(self, store: ms.MemoryStore, md_path: Path) -> None:
        big = "# 大きい\n\n" + ("あ" * 3000)
        md_path.write_text(big, encoding="utf-8")
        mgr = mm.MemoryMdManager(md_path, store, max_chars=2200)
        assert mgr.needs_archive()


# ---------------------------------------------------------------------------
# archive_to_store
# ---------------------------------------------------------------------------


class TestArchiveToStore:
    def _make_md(self, sections: list[tuple[str, str]]) -> str:
        """ヘッダタイトルと本文のリストから MEMORY.md テキストを作る。"""
        parts = []
        for title, body in sections:
            parts.append(f"## {title}\n\n{body}\n\n")
        return "".join(parts)

    def test_archive_when_under_cap_does_nothing(self, store: ms.MemoryStore, md_path: Path) -> None:
        text = self._make_md([("直近", "短い本文")])
        md_path.write_text(text, encoding="utf-8")
        mgr = mm.MemoryMdManager(md_path, store, max_chars=2200)
        report = mgr.archive_to_store()
        assert report.archived_titles == []
        assert report.archived_entry_ids == []
        # 元ファイルそのまま
        assert md_path.read_text(encoding="utf-8") == text

    def test_archive_moves_oldest_archivable(self, store: ms.MemoryStore, md_path: Path) -> None:
        # 3 つの archivable と 1 つの protected。max_chars を小さく設定して 1 つ archive を強制
        sections = [
            ("古い日常 1", "本文" * 100),
            ("五つの誓い", "誓い本文"),
            ("中くらいの日常 2", "本文" * 100),
            ("新しい日常 3", "本文" * 100),
        ]
        text = self._make_md(sections)
        md_path.write_text(text, encoding="utf-8")
        mgr = mm.MemoryMdManager(md_path, store, max_chars=600)
        report = mgr.archive_to_store()
        # 「古い日常 1」が最初の archivable なので最初に移される
        assert "古い日常 1" in report.archived_titles
        # 五つの誓いは絶対に移されない
        assert "五つの誓い" not in report.archived_titles

    def test_archive_protected_never_moved(self, store: ms.MemoryStore, md_path: Path) -> None:
        sections = [
            ("五つの誓い", "誓い本文"),
            ("記念日", "5/10 誕生日"),
            ("命日", "5/28 母上"),
            ("日常", "本文" * 200),
        ]
        text = self._make_md(sections)
        md_path.write_text(text, encoding="utf-8")
        mgr = mm.MemoryMdManager(md_path, store, max_chars=300)
        report = mgr.archive_to_store()
        # archive されたのは「日常」だけ
        assert "日常" in report.archived_titles
        for protected_title in ["五つの誓い", "記念日", "命日"]:
            assert protected_title not in report.archived_titles

    def test_archive_records_to_state_db(self, store: ms.MemoryStore, md_path: Path) -> None:
        sections = [("日常", "古い本文" * 200), ("五つの誓い", "誓い")]
        text = self._make_md(sections)
        md_path.write_text(text, encoding="utf-8")
        mgr = mm.MemoryMdManager(md_path, store, max_chars=300)
        report = mgr.archive_to_store()
        # state.db に source=memory_md_archive で記録されている
        entries = store.recall(limit=10)
        assert len(entries) == 1
        assert entries[0].source == "memory_md_archive"
        assert entries[0].importance == ms.IMPORTANCE_NORMAL
        assert entries[0].metadata["section_title"] == "日常"

    def test_archive_writes_back_md(self, store: ms.MemoryStore, md_path: Path) -> None:
        sections = [("日常", "本文" * 300), ("五つの誓い", "誓い")]
        text = self._make_md(sections)
        md_path.write_text(text, encoding="utf-8")
        mgr = mm.MemoryMdManager(md_path, store, max_chars=300)
        mgr.archive_to_store(write_back=True)
        new_text = md_path.read_text(encoding="utf-8")
        assert "## 五つの誓い" in new_text
        assert "## 日常" not in new_text

    def test_archive_creates_backup(self, store: ms.MemoryStore, md_path: Path) -> None:
        sections = [("日常", "本文" * 300), ("五つの誓い", "誓い")]
        text = self._make_md(sections)
        md_path.write_text(text, encoding="utf-8")
        mgr = mm.MemoryMdManager(md_path, store, max_chars=300)
        mgr.archive_to_store(write_back=True)
        backup = md_path.with_suffix(".md.bak")
        assert backup.exists()
        assert backup.read_text(encoding="utf-8") == text

    def test_archive_dry_run(self, store: ms.MemoryStore, md_path: Path) -> None:
        sections = [("日常", "本文" * 300), ("五つの誓い", "誓い")]
        text = self._make_md(sections)
        md_path.write_text(text, encoding="utf-8")
        mgr = mm.MemoryMdManager(md_path, store, max_chars=300)
        report = mgr.archive_to_store(write_back=False)
        # state.db には記録されている (dry-run でも DB 操作は行われる)
        assert len(report.archived_entry_ids) > 0
        # しかし MEMORY.md は変更されていない
        assert md_path.read_text(encoding="utf-8") == text

    def test_archive_all_protected_no_op(self, store: ms.MemoryStore, md_path: Path) -> None:
        sections = [("五つの誓い", "本文" * 300), ("記念日", "本文" * 300)]
        text = self._make_md(sections)
        md_path.write_text(text, encoding="utf-8")
        mgr = mm.MemoryMdManager(md_path, store, max_chars=300)
        report = mgr.archive_to_store()
        # 全 protected なので archive できない
        assert report.archived_titles == []
        assert report.over_cap_after  # 上限超過のまま

    def test_archive_target_chars(self, store: ms.MemoryStore, md_path: Path) -> None:
        sections = [
            ("日常 1", "あ" * 100),
            ("日常 2", "い" * 100),
            ("日常 3", "う" * 100),
        ]
        text = self._make_md(sections)
        md_path.write_text(text, encoding="utf-8")
        mgr = mm.MemoryMdManager(md_path, store, max_chars=200)
        report = mgr.archive_to_store(target_chars=150)
        # 150 文字以下になるまで archive する
        assert report.final_chars <= 200  # max_chars 以下 (target はもっと厳しい)

    def test_archive_invalid_target_chars_raises(self, store: ms.MemoryStore, md_path: Path) -> None:
        md_path.write_text("# x\n", encoding="utf-8")
        mgr = mm.MemoryMdManager(md_path, store)
        with pytest.raises(ValueError):
            mgr.archive_to_store(target_chars=0)


# ---------------------------------------------------------------------------
# restore_archived_section
# ---------------------------------------------------------------------------


class TestRestoreArchivedSection:
    def test_restore_finds_archived(self, store: ms.MemoryStore, md_path: Path) -> None:
        # 直接 store に archive 形式で記録
        store.record(
            content="## 古い日常\n\n本文の中身\n",
            importance=ms.IMPORTANCE_NORMAL,
            source="memory_md_archive",
            metadata={"section_title": "古い日常"},
        )
        mgr = mm.MemoryMdManager(md_path, store)
        result = mgr.restore_archived_section("古い日常")
        assert result is not None
        assert "古い日常" in result

    def test_restore_returns_none_when_not_found(self, store: ms.MemoryStore, md_path: Path) -> None:
        mgr = mm.MemoryMdManager(md_path, store)
        assert mgr.restore_archived_section("存在しない") is None

    def test_restore_skips_non_archive_entries(self, store: ms.MemoryStore, md_path: Path) -> None:
        # source=conversation で記録された同名のものは無視される
        store.record(content="ご飯", source="conversation")
        mgr = mm.MemoryMdManager(md_path, store)
        assert mgr.restore_archived_section("ご飯") is None


# ---------------------------------------------------------------------------
# promote_protected_sections
# ---------------------------------------------------------------------------


class TestPromoteProtectedSections:
    def test_promote_copies_protected_to_table(self, store: ms.MemoryStore, md_path: Path) -> None:
        text = "## 五つの誓い\n\n誓い本文\n\n## 日常\n\n本文\n"
        md_path.write_text(text, encoding="utf-8")
        mgr = mm.MemoryMdManager(md_path, store)
        ids = mgr.promote_protected_sections()
        assert len(ids) == 1
        protected = store.list_protected()
        assert len(protected) == 1
        assert "誓い" in protected[0].content

    def test_promote_idempotent(self, store: ms.MemoryStore, md_path: Path) -> None:
        text = "## 記念日\n\n5/10\n"
        md_path.write_text(text, encoding="utf-8")
        mgr = mm.MemoryMdManager(md_path, store)
        ids1 = mgr.promote_protected_sections()
        ids2 = mgr.promote_protected_sections()
        assert len(ids1) == 1
        assert len(ids2) == 0  # 重複は防がれる
        assert len(store.list_protected()) == 1

    def test_promote_skips_non_protected(self, store: ms.MemoryStore, md_path: Path) -> None:
        text = "## 日常\n\n本文\n"
        md_path.write_text(text, encoding="utf-8")
        mgr = mm.MemoryMdManager(md_path, store)
        ids = mgr.promote_protected_sections()
        assert ids == []
        assert store.list_protected() == []

    def test_promote_handles_empty_md(self, store: ms.MemoryStore, md_path: Path) -> None:
        mgr = mm.MemoryMdManager(md_path, store)
        ids = mgr.promote_protected_sections()
        assert ids == []
