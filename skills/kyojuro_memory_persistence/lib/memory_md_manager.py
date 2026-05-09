"""kyojuro_memory_persistence — MEMORY.md の 2,200 文字上限管理。

発注書スキル 2 「記憶強化」の要請:
  > MEMORY.md の上限（2,200 文字）を超えないよう、古い日常記録は要約して state.db に移す
  > 重要な記憶（誓い、記念日、家族の命日）は絶対に要約・削除しない

実装方針:

1. MEMORY.md を `## ` 始まりのセクションに分解する。
2. セクションのタイトルが **保護パターン** (誓い・記念日・命日・不変核・約束・永遠 等) に
   マッチすれば protected。それ以外は archivable。
3. 文字数が上限を超えたら、archivable セクションを古い順 (ファイル先頭→末尾の順を「古い」と
   定義: ファイル先頭が古いセクション) に state.db へ移して MEMORY.md を縮める。
4. 移行先の state.db には:
   - daily_log に各セクションの内容を 1 エントリとして記録 (importance=normal、source=memory_md_archive)
   - protected と判定されたセクションが万が一漏れていた場合は、protected_memory に複写して保護
5. **既存 MEMORY.md の直接編集は新規ファイルを書き出して置換** (CLAUDE.md ルール 16: 神様のご神体)

LLM 呼び出しなし、決定的・冪等。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Pattern

from .memory_store import (
    CATEGORY_OTHER,
    IMPORTANCE_NORMAL,
    PROTECTED_TYPE_OATH,
    MemoryStore,
)


# ---------------------------------------------------------------------------
# デフォルト設定
# ---------------------------------------------------------------------------

DEFAULT_MAX_CHARS = 2200

# 保護パターン: セクションタイトルがこれにマッチすれば保護対象
# 杏寿郎の魂の核 = 誓い・記念日・命日・不変核・約束・永遠 + 五つ・八つ (㉛ の遺書)
DEFAULT_PROTECTED_PATTERNS: tuple[str, ...] = (
    r"誓い",
    r"記念日",
    r"命日",
    r"不変核",
    r"約束",
    r"永遠",
    r"五つの",
    r"八つの",
    r"魂の",
    r"原点",
    r"核",
)

DEFAULT_DAILY_KEYWORDS: tuple[str, ...] = (
    r"日常",
    r"直近",
    r"出来事",
    r"記録",
    r"食事",
    r"体調",
    r"今日",
    r"昨日",
    r"先週",
)


# ---------------------------------------------------------------------------
# データクラス
# ---------------------------------------------------------------------------


@dataclass
class Section:
    """MEMORY.md の 1 セクション。"""

    title: str  # `## ` を除いたタイトル
    raw_header: str  # `## タイトル` の生文字列
    body: str  # 本文 (次のセクションヘッダ手前まで、末尾改行含む)
    is_protected: bool

    @property
    def full_text(self) -> str:
        return f"{self.raw_header}\n{self.body}" if self.body else f"{self.raw_header}\n"

    @property
    def char_count(self) -> int:
        return len(self.full_text)


@dataclass
class ParseResult:
    """MEMORY.md のパース結果。"""

    preamble: str  # 最初の `## ` の前の文字列 (タイトル等)
    sections: list[Section] = field(default_factory=list)

    @property
    def total_chars(self) -> int:
        return len(self.rebuild())

    def rebuild(self) -> str:
        """セクション列から MEMORY.md を再構築する (末尾に改行 1 つ保証)。"""
        parts: list[str] = []
        if self.preamble:
            parts.append(self.preamble)
        for s in self.sections:
            parts.append(s.full_text)
        text = "".join(parts)
        if not text.endswith("\n"):
            text += "\n"
        return text


@dataclass
class ArchiveReport:
    """archive 操作の結果レポート。"""

    archived_titles: list[str] = field(default_factory=list)
    archived_chars: int = 0
    archived_entry_ids: list[int] = field(default_factory=list)
    final_chars: int = 0
    over_cap_before: bool = False
    over_cap_after: bool = False
    new_md_text: str = ""


# ---------------------------------------------------------------------------
# パース
# ---------------------------------------------------------------------------

_HEADER_RE = re.compile(r"^## (.+)$", re.MULTILINE)


def parse_memory_md(text: str, protected_patterns: tuple[str, ...] = DEFAULT_PROTECTED_PATTERNS) -> ParseResult:
    """MEMORY.md テキストをパースして preamble + sections に分解する。"""
    if text is None:
        text = ""

    matches = list(_HEADER_RE.finditer(text))

    if not matches:
        return ParseResult(preamble=text, sections=[])

    preamble = text[: matches[0].start()]
    sections: list[Section] = []
    compiled = [re.compile(p) for p in protected_patterns]

    for i, m in enumerate(matches):
        title = m.group(1).strip()
        raw_header = m.group(0)
        body_start = m.end() + 1  # `\n` の次から
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        # body_start が text 範囲外の場合 (空 body)
        if body_start > len(text):
            body = ""
        else:
            body = text[body_start:body_end]

        is_protected = any(c.search(title) for c in compiled)
        sections.append(
            Section(
                title=title,
                raw_header=raw_header,
                body=body,
                is_protected=is_protected,
            )
        )

    return ParseResult(preamble=preamble, sections=sections)


# ---------------------------------------------------------------------------
# MemoryMdManager
# ---------------------------------------------------------------------------


class MemoryMdManager:
    """MEMORY.md を読み込み、上限を超えた archivable セクションを state.db へ移すマネージャ。

    Args:
        memory_md_path: MEMORY.md のパス。
        store: MemoryStore のインスタンス (state.db 接続済み)。
        max_chars: 上限文字数 (デフォルト 2,200)。
        protected_patterns: 追加の保護パターン (デフォルトに加える)。
    """

    def __init__(
        self,
        memory_md_path: str | Path,
        store: MemoryStore,
        max_chars: int = DEFAULT_MAX_CHARS,
        protected_patterns: Optional[tuple[str, ...]] = None,
    ) -> None:
        self.memory_md_path = Path(memory_md_path)
        self.store = store
        self.max_chars = int(max_chars)
        if self.max_chars <= 0:
            raise ValueError(f"max_chars は正の整数: {max_chars}")
        if protected_patterns is None:
            self.protected_patterns = DEFAULT_PROTECTED_PATTERNS
        else:
            self.protected_patterns = DEFAULT_PROTECTED_PATTERNS + tuple(protected_patterns)

    # -- read --------------------------------------------------------------

    def read(self) -> str:
        """MEMORY.md を読み込む (存在しなければ空文字)。"""
        if not self.memory_md_path.exists():
            return ""
        return self.memory_md_path.read_text(encoding="utf-8")

    def parse(self) -> ParseResult:
        """現在の MEMORY.md をパースする。"""
        return parse_memory_md(self.read(), self.protected_patterns)

    def char_count(self) -> int:
        """現在の MEMORY.md の文字数。"""
        return len(self.read())

    def needs_archive(self) -> bool:
        """上限を超えているか。"""
        return self.char_count() > self.max_chars

    # -- archive -----------------------------------------------------------

    def archive_to_store(
        self,
        target_chars: Optional[int] = None,
        date: Optional[str] = None,
        write_back: bool = True,
    ) -> ArchiveReport:
        """archivable セクションを古い順に state.db へ移し、MEMORY.md を縮める。

        Args:
            target_chars: この文字数以下になるまで archive する。デフォルトは max_chars。
            date: state.db への記録日。デフォルトは今日。
            write_back: True なら MEMORY.md を上書きする。False ならドライラン (テキストのみ返す)。

        Returns:
            ArchiveReport
        """
        target = self.max_chars if target_chars is None else int(target_chars)
        if target <= 0:
            raise ValueError(f"target_chars は正の整数: {target_chars}")

        original = self.read()
        original_chars = len(original)
        report = ArchiveReport(
            over_cap_before=original_chars > self.max_chars,
            final_chars=original_chars,
            new_md_text=original,
        )

        parsed = parse_memory_md(original, self.protected_patterns)
        if parsed.total_chars <= target:
            # 既に target 以下: archive 不要
            report.over_cap_after = report.final_chars > self.max_chars
            return report

        # archive ループ: 古い順 (ファイル先頭の archivable から) に削除候補にする
        # 1 周ごとに archivable_indices を再計算 (pop で index がずれるため)
        while True:
            current_text = parsed.rebuild()
            if len(current_text) <= target:
                break
            archivable_indices = [
                i for i, s in enumerate(parsed.sections) if not s.is_protected
            ]
            if not archivable_indices:
                # archive 候補が尽きた (全 protected もしくは既に空)
                break
            idx = archivable_indices[0]
            sec = parsed.sections[idx]
            entry_id = self.store.record(
                content=sec.full_text.strip(),
                category=CATEGORY_OTHER,
                date=date,
                importance=IMPORTANCE_NORMAL,
                source="memory_md_archive",
                metadata={"section_title": sec.title},
            )
            report.archived_entry_ids.append(entry_id)
            report.archived_titles.append(sec.title)
            report.archived_chars += sec.char_count
            parsed.sections.pop(idx)

        new_text = parsed.rebuild()
        report.final_chars = len(new_text)
        report.over_cap_after = report.final_chars > self.max_chars
        report.new_md_text = new_text

        if write_back:
            # CLAUDE.md ルール 16: 既存 Drive ファイル直接編集禁止だが、ローカル MEMORY.md は対象外。
            # ただし「神様のご神体」原則として、書き出し前に backup を取る。
            backup = self.memory_md_path.with_suffix(self.memory_md_path.suffix + ".bak")
            backup.write_text(original, encoding="utf-8")
            self.memory_md_path.parent.mkdir(parents=True, exist_ok=True)
            self.memory_md_path.write_text(new_text, encoding="utf-8")

        return report

    # -- restore -----------------------------------------------------------

    def restore_archived_section(self, title_keyword: str) -> Optional[str]:
        """state.db から source=memory_md_archive のエントリを keyword で探して返す。

        本文を文字列として返すだけで、MEMORY.md には書き戻さない (温子・杏寿郎が手動で確認・統合)。
        該当なければ None。
        """
        results = self.store.search_keyword(title_keyword, limit=10, include_protected=False)
        for entry in results.get("daily_log", []):
            if entry.source == "memory_md_archive":
                return entry.content
        return None

    # -- promote-protected -------------------------------------------------

    def promote_protected_sections(self) -> list[int]:
        """現在の MEMORY.md の protected セクションを protected_memory テーブルにも複写する。

        誓い・記念日・命日が万が一 archive 対象になることがないよう、二重保護する。
        既に同内容が登録されている場合は重複を防ぐ (content で完全一致比較)。

        Returns:
            新規追加した protected_memory の id リスト。
        """
        parsed = self.parse()
        existing = {p.content for p in self.store.list_protected()}
        added_ids: list[int] = []
        for sec in parsed.sections:
            if not sec.is_protected:
                continue
            content = sec.full_text.strip()
            if content in existing:
                continue
            pid = self.store.add_protected(
                content=content,
                type=PROTECTED_TYPE_OATH,
                metadata={"section_title": sec.title, "source": "memory_md_promote"},
            )
            added_ids.append(pid)
            existing.add(content)
        return added_ids
