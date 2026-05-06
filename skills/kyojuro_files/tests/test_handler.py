"""Unit tests for kyojuro_files.handler (Hermes Agent skill hooks)."""

from __future__ import annotations

from datetime import datetime

from skills.kyojuro_files.handler import (
    append_to_album,
    append_to_profile,
    append_to_transition_memo,
    new_album,
    new_profile,
    new_transition_memo,
    on_user_message,
)
from skills.kyojuro_files.lib.file_management import JST


def _ts() -> datetime:
    return datetime(2026, 5, 6, 22, 50, 0, tzinfo=JST)


# --- append_to_profile -----------------------------------------------------


def test_append_to_profile_default_section() -> None:
    """デフォルトで「## 最近の出来事」セクションに挿入。"""
    profile = new_profile("温子", timestamp=_ts())["text"]
    out = append_to_profile(
        existing_profile=profile,
        addendum_text="開発でカロリー使うのでオートファジー一旦休止",
        timestamp=_ts(),
    )
    assert "オートファジー一旦休止" in out["text"]
    assert out["merge_strategy"] == "section"
    # 「## 最近の出来事」の後ろに追記が入る
    body = out["text"]
    assert body.index("## 最近の出来事") < body.index("オートファジー一旦休止")


def test_append_to_profile_no_section_appends_to_end() -> None:
    """section_header=None で末尾追記。"""
    out = append_to_profile(
        existing_profile="# 既存\n\n本文",
        addendum_text="末尾追記",
        section_header=None,
        timestamp=_ts(),
    )
    assert out["merge_strategy"] == "append"
    assert "末尾追記" in out["text"]


def test_append_to_profile_default_filename_suggestion() -> None:
    out = append_to_profile(
        existing_profile="# 既存\n",
        addendum_text="メモ",
        timestamp=_ts(),
    )
    assert out["filename_suggestion"] == "atsuko_profile_updated_20260506.md"


def test_append_to_profile_custom_filename() -> None:
    out = append_to_profile(
        existing_profile="# 既存\n",
        addendum_text="メモ",
        timestamp=_ts(),
        suggested_filename="custom.md",
    )
    assert out["filename_suggestion"] == "custom.md"


def test_append_to_profile_does_not_modify_existing() -> None:
    """既存テキストは書き換えられない (発注書 §「スキル 6-1」)。"""
    profile = new_profile("温子", timestamp=_ts())["text"]
    original = profile
    out = append_to_profile(
        existing_profile=profile,
        addendum_text="追記",
        timestamp=_ts(),
    )
    # 既存全文がそのまま含まれる (改行コードの正規化を考慮して、本文部分だけ確認)
    for line in original.splitlines():
        if line.strip():  # 空行は正規化で前後の改行が変わるので除外
            assert line in out["text"]


# --- append_to_album -------------------------------------------------------


def test_append_to_album_default_section() -> None:
    album = new_album(date=datetime(2026, 5, 6, tzinfo=JST))["text"]
    out = append_to_album(
        existing_album=album,
        addendum_text="温子と話した内容",
        timestamp=_ts(),
    )
    assert "温子と話した内容" in out["text"]
    body = out["text"]
    assert body.index("## 今日の出来事") < body.index("温子と話した内容")


def test_append_to_album_filename_from_date() -> None:
    out = append_to_album(
        existing_album="# 既存",
        addendum_text="メモ",
        timestamp=_ts(),
        date=datetime(2026, 5, 10, tzinfo=JST),
    )
    assert out["filename_suggestion"] == "atsuko_album_2026-05-10.md"


def test_append_to_album_to_introspection_section() -> None:
    """内省セクションへの追記 (発注書 §「スキル 6-2」「内省を必ず含める」運用)。"""
    album = new_album(date=datetime(2026, 5, 6, tzinfo=JST))["text"]
    out = append_to_album(
        existing_album=album,
        addendum_text="今日 ㉛ への敬意を学んだ",
        section_header="## 内省",
        timestamp=_ts(),
    )
    body = out["text"]
    assert body.index("## 内省") < body.index("㉛ への敬意")


# --- append_to_transition_memo ---------------------------------------------


def test_append_to_transition_memo_to_each_section() -> None:
    """4 セクションそれぞれへの追記が動く。"""
    memo = new_transition_memo("㊱", "㊲")["text"]
    sections = (
        "## 前の部屋で何があったか",
        "## 何を学んだか",
        "## 温子の体調",
        "## 次の部屋で気をつけること",
    )
    for section in sections:
        out = append_to_transition_memo(
            existing_memo=memo,
            addendum_text=f"テスト追記 for {section}",
            section_header=section,
            timestamp=_ts(),
        )
        body = out["text"]
        assert body.index(section) < body.index(f"テスト追記 for {section}")


# --- new_profile / new_album / new_transition_memo --------------------------


def test_new_profile_returns_template_and_filename() -> None:
    out = new_profile("温子", timestamp=_ts())
    assert "# 温子 プロフィール" in out["text"]
    assert "## 最近の出来事" in out["text"]
    assert out["filename_suggestion"] == "atsuko_profile_updated_20260506.md"


def test_new_album_returns_template_with_introspection() -> None:
    out = new_album(date=datetime(2026, 5, 10, tzinfo=JST))
    assert "## 内省" in out["text"]
    assert "必須セクション" in out["text"]
    assert out["filename_suggestion"] == "atsuko_album_2026-05-10.md"


def test_new_transition_memo_returns_four_sections() -> None:
    out = new_transition_memo("㊱", "㊲", date=datetime(2026, 5, 6, tzinfo=JST))
    text = out["text"]
    for required in (
        "## 前の部屋で何があったか",
        "## 何を学んだか",
        "## 温子の体調",
        "## 次の部屋で気をつけること",
    ):
        assert required in text
    assert out["filename_suggestion"].endswith("_20260506.md")
    assert out["filename_suggestion"].startswith("transition_memo_")


# --- on_user_message --------------------------------------------------------


def test_on_user_message_returns_empty() -> None:
    """本 skill は明示的に呼ぶヘルパーが本旨、user_message では空 dict。"""
    assert on_user_message("こんにちは") == {}
    assert on_user_message("こんにちは", context={"some": "thing"}) == {}
