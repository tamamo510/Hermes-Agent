"""Unit tests for kyojuro_files.lib.file_management.

決定性: すべてのテストは固定 datetime を直接渡す。
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from skills.kyojuro_files.lib.file_management import (
    DriveSafeResult,
    JST,
    album_template,
    default_album_filename,
    default_profile_filename,
    default_transition_memo_filename,
    merge_addendum,
    merge_into_section,
    produce_drive_ready,
    profile_template,
    to_drive_safe_text,
    transition_memo_template,
    validate_drive_text,
)


def _ts() -> datetime:
    """共通の固定タイムスタンプ (JST aware)。"""
    return datetime(2026, 5, 6, 22, 50, 0, tzinfo=JST)


# --- merge_addendum ---------------------------------------------------------


def test_merge_addendum_to_empty() -> None:
    out = merge_addendum("", "今日のメモ", timestamp=_ts())
    assert "今日のメモ" in out
    assert "2026-05-06T22:50:00+09:00" in out
    assert "by 杏寿郎" in out
    assert out.endswith("\n")


def test_merge_addendum_to_existing() -> None:
    existing = "# 温子プロフィール\n\n## 基本\n\n名前: 温子\n"
    out = merge_addendum(existing, "気圧低下で頭痛", timestamp=_ts())
    # 既存テキストはそのまま保持
    assert "# 温子プロフィール" in out
    assert "## 基本" in out
    assert "名前: 温子" in out
    # 追記が末尾にある
    assert "気圧低下で頭痛" in out
    assert out.index("気圧低下で頭痛") > out.index("名前: 温子")


def test_merge_addendum_does_not_modify_existing() -> None:
    """既存テキストの中身は変わらず、末尾に追加されるだけ。"""
    existing = "本文\n中身\n"
    out = merge_addendum(existing, "追記", timestamp=_ts())
    # 既存の本文がそのまま含まれている (順序保持)
    assert out.index("本文") < out.index("中身") < out.index("追記")


def test_merge_addendum_updated_by_custom() -> None:
    out = merge_addendum("既存", "追記", timestamp=_ts(), updated_by="温子")
    assert "by 温子" in out


def test_merge_addendum_default_timestamp_is_jst() -> None:
    """timestamp=None で例外を出さず、結果に JST タイムスタンプが入る。"""
    out = merge_addendum("既存", "追記")
    assert "+09:00" in out


def test_merge_addendum_block_format() -> None:
    """追記ブロックの開始/終了マーカーが含まれる。"""
    out = merge_addendum("", "中身", timestamp=_ts())
    assert "<!-- 追記 2026-05-06T22:50:00+09:00 by 杏寿郎 -->" in out
    assert "<!-- /追記 -->" in out


# --- merge_into_section ----------------------------------------------------


def test_merge_into_section_existing_section() -> None:
    existing = (
        "# プロフィール\n\n"
        "## 基本\n\n名前: 温子\n\n"
        "## 最近の出来事\n\n(自動追記領域)\n"
    )
    out = merge_into_section(
        existing,
        "## 最近の出来事",
        "PR #92 マージ完了",
        timestamp=_ts(),
    )
    assert "PR #92 マージ完了" in out
    assert "名前: 温子" in out  # 既存セクションは保持
    # 追記は「## 最近の出来事」の中、すなわち「## 基本」の後ろ
    assert out.index("## 基本") < out.index("## 最近の出来事") < out.index("PR #92")


def test_merge_into_section_creates_new_when_missing() -> None:
    """セクションが存在しなければ末尾に新設して追記。"""
    out = merge_into_section(
        "# 既存\n\n本文\n",
        "## 新セクション",
        "追記内容",
        timestamp=_ts(),
    )
    assert "## 新セクション" in out
    assert "追記内容" in out
    assert out.index("本文") < out.index("## 新セクション") < out.index("追記内容")


def test_merge_into_section_with_subsequent_section() -> None:
    """同レベルの次セクションがあるとき、その直前に追記が入る (越境しない)。"""
    existing = (
        "# プロフィール\n\n"
        "## A\n\nA 本文\n\n"
        "## B\n\nB 本文\n"
    )
    out = merge_into_section(existing, "## A", "A 追記", timestamp=_ts())
    # A 追記は B より前にある
    assert out.index("A 追記") < out.index("## B")


def test_merge_into_section_preserves_existing_content() -> None:
    """既存セクション本文は書き換えられず、追記が末尾に足される。"""
    existing = (
        "## メモ\n\n古い記述 1\n古い記述 2\n"
    )
    out = merge_into_section(existing, "## メモ", "新しい記述", timestamp=_ts())
    assert "古い記述 1" in out
    assert "古い記述 2" in out
    assert "新しい記述" in out
    assert out.index("古い記述 1") < out.index("新しい記述")


# --- to_drive_safe_text ----------------------------------------------------


def test_to_drive_safe_text_clean_input() -> None:
    """元からクリーンなテキストは変わらず issues は空。"""
    result = to_drive_safe_text("クリーンな本文\n")
    assert isinstance(result, DriveSafeResult)
    assert result.text == "クリーンな本文\n"
    assert result.issues == ()


def test_to_drive_safe_text_strips_bom() -> None:
    result = to_drive_safe_text("﻿温子\n")
    assert not result.text.startswith("﻿")
    assert any("BOM" in i for i in result.issues)


def test_to_drive_safe_text_normalizes_crlf_to_lf() -> None:
    result = to_drive_safe_text("行 1\r\n行 2\r\n")
    assert "\r" not in result.text
    assert result.text == "行 1\n行 2\n"
    assert any("CRLF" in i for i in result.issues)


def test_to_drive_safe_text_normalizes_lone_cr_to_lf() -> None:
    result = to_drive_safe_text("行 1\r行 2")
    assert "\r" not in result.text
    assert result.text == "行 1\n行 2\n"
    assert any("CR 単独" in i for i in result.issues)


def test_to_drive_safe_text_strips_control_chars() -> None:
    result = to_drive_safe_text("本文\x00中身\x07\n")
    assert "\x00" not in result.text
    assert "\x07" not in result.text
    assert any("制御文字" in i for i in result.issues)


def test_to_drive_safe_text_preserves_tab() -> None:
    """タブ (\\t) は制御文字だが除去対象外 (人間が打つ正当な文字)。"""
    result = to_drive_safe_text("col1\tcol2\n")
    assert "\t" in result.text
    assert not any("制御文字" in i for i in result.issues)


def test_to_drive_safe_text_ensures_trailing_newline() -> None:
    result = to_drive_safe_text("末尾改行なし")
    assert result.text.endswith("\n")
    assert any("末尾改行" in i for i in result.issues)


def test_to_drive_safe_text_empty_input() -> None:
    result = to_drive_safe_text("")
    assert result.text == ""
    assert result.issues == ()


def test_to_drive_safe_text_combined_issues() -> None:
    result = to_drive_safe_text("﻿温子\r\nプロフィール\rです")
    assert result.text == "温子\nプロフィール\nです\n"
    assert any("BOM" in i for i in result.issues)
    assert any("CRLF" in i for i in result.issues)
    assert any("CR 単独" in i for i in result.issues)
    assert any("末尾改行" in i for i in result.issues)


# --- validate_drive_text ----------------------------------------------------


def test_validate_drive_text_clean() -> None:
    assert validate_drive_text("本文\n") == []


def test_validate_drive_text_detects_bom() -> None:
    issues = validate_drive_text("﻿本文\n")
    assert any("BOM" in i for i in issues)


def test_validate_drive_text_detects_crlf() -> None:
    issues = validate_drive_text("a\r\nb\n")
    assert any("CRLF" in i for i in issues)


def test_validate_drive_text_detects_lone_cr() -> None:
    issues = validate_drive_text("a\rb\n")
    assert any("CR 単独" in i for i in issues)


def test_validate_drive_text_detects_missing_trailing_newline() -> None:
    issues = validate_drive_text("末尾改行なし")
    assert any("末尾改行" in i for i in issues)


# --- ファイル名生成 ---------------------------------------------------------


def test_default_album_filename() -> None:
    d = datetime(2026, 5, 6, 12, 0, tzinfo=JST)
    assert default_album_filename(d) == "atsuko_album_2026-05-06.md"


def test_default_album_filename_converts_utc_to_jst() -> None:
    """UTC datetime は JST に変換されてから日付化される。"""
    utc_late = datetime(2026, 5, 5, 18, 0, tzinfo=timezone.utc)  # JST: 5/6 03:00
    assert default_album_filename(utc_late) == "atsuko_album_2026-05-06.md"


def test_default_profile_filename() -> None:
    d = datetime(2026, 5, 6, 22, 50, tzinfo=JST)
    assert default_profile_filename(d) == "atsuko_profile_updated_20260506.md"


def test_default_transition_memo_filename() -> None:
    d = datetime(2026, 5, 6, tzinfo=JST)
    fname = default_transition_memo_filename("㊱", "㊲", d)
    assert fname.startswith("transition_memo_")
    assert fname.endswith("_20260506.md")


def test_default_transition_memo_filename_slugifies() -> None:
    """ファイル名に使えない文字 (「㊱」のような特殊文字) はアンダースコアに置換。"""
    d = datetime(2026, 5, 6, tzinfo=JST)
    fname = default_transition_memo_filename("room 35!", "room 36!", d)
    # 英数 + _ + - のみ
    import re
    body = fname.replace("transition_memo_", "").replace(".md", "")
    assert re.match(r"^[a-zA-Z0-9_-]+$", body)


# --- テンプレ ---------------------------------------------------------------


def test_profile_template_contains_required_sections() -> None:
    text = profile_template("温子")
    assert "# 温子 プロフィール" in text
    assert "## 基本情報" in text
    assert "## 体質・健康情報" in text
    assert "## 現在のリズム" in text  # kyojuro_time 連携先
    assert "## 大切な日" in text  # SOUL.md §9 連動
    assert "## 最近の出来事" in text
    # 追記統合方式の説明
    assert "追記統合方式" in text or "追記統合" in text


def test_album_template_includes_required_introspection() -> None:
    """発注書 §「スキル 6-2」の「内省を必ず含める」を遵守。"""
    text = album_template(datetime(2026, 5, 6, tzinfo=JST))
    assert "アルバム" in text
    assert "## 内省" in text
    assert "必須セクション" in text  # 必須であることが明示されている


def test_album_template_includes_date() -> None:
    text = album_template(datetime(2026, 5, 10, tzinfo=JST))  # 杏寿郎の誕生日 = 日曜
    assert "2026年05月10日" in text
    assert "日" in text  # 曜日表示


def test_transition_memo_template_four_sections() -> None:
    """発注書 §「スキル 6-3」の 4 セクション構造を遵守。"""
    text = transition_memo_template("㊱", "㊲")
    assert "## 前の部屋で何があったか" in text
    assert "## 何を学んだか" in text
    assert "## 温子の体調" in text
    assert "## 次の部屋で気をつけること" in text
    assert "㊱" in text
    assert "㊲" in text


# --- produce_drive_ready ---------------------------------------------------


def test_produce_drive_ready_section_strategy() -> None:
    existing = "# プロフィール\n\n## 最近の出来事\n\n(自動追記領域)\n"
    out = produce_drive_ready(
        existing,
        "PR #92 マージ完了",
        section_header="## 最近の出来事",
        timestamp=_ts(),
    )
    assert out["merge_strategy"] == "section"
    assert "PR #92 マージ完了" in out["text"]
    assert out["filename_suggestion"] == ""  # 指定なし
    assert isinstance(out["applied_fixups"], list)


def test_produce_drive_ready_append_strategy() -> None:
    out = produce_drive_ready(
        "# 既存\n\n本文",
        "今日のメモ",
        timestamp=_ts(),
    )
    assert out["merge_strategy"] == "append"


def test_produce_drive_ready_filename_suggestion() -> None:
    out = produce_drive_ready(
        "",
        "メモ",
        timestamp=_ts(),
        suggested_filename="atsuko_profile_updated_20260506.md",
    )
    assert out["filename_suggestion"] == "atsuko_profile_updated_20260506.md"


def test_produce_drive_ready_records_fixups_for_dirty_input() -> None:
    """既存に CRLF が含まれていたら applied_fixups に記録される。"""
    out = produce_drive_ready(
        "本文\r\n中身",  # CRLF + 末尾改行なし
        "追記",
        timestamp=_ts(),
    )
    # to_drive_safe_text が修正した内容が記録される
    assert any("CRLF" in fix for fix in out["applied_fixups"])
    # 完成版は LF 統一 + 末尾改行あり
    assert "\r" not in out["text"]
    assert out["text"].endswith("\n")


def test_produce_drive_ready_clean_input_no_fixups() -> None:
    """既存がクリーンなら applied_fixups は空。"""
    out = produce_drive_ready("# 既存\n", "追記", timestamp=_ts())
    assert out["applied_fixups"] == []
