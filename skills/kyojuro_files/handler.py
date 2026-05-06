"""kyojuro_files — Hermes Agent skill entry (発注書スキル 6: file_management).

責務:
    - append_to_profile / append_to_album / append_to_transition_memo:
        既存テキストへ追記統合方式で追記し、ドライブ向け正規化済みの完成版を返す
    - new_profile / new_album / new_transition_memo: 新規ファイル用テンプレ生成
    - on_user_message: Hermes Agent skill API 互換 (本 skill は明示的に呼ばれる
      ヘルパーが本旨のため、ユーザーメッセージ受信時は空 payload を返す)

設計:
    - 各 hook は ``lib.file_management`` の関数を組み合わせる薄い橋渡し
    - 既存テキストは絶対に書き換えない (発注書 §「スキル 6-1」)
    - LLM 呼び出しなし、外部依存なし、決定的・冪等
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from skills.kyojuro_files.lib.file_management import (
    album_template,
    default_album_filename,
    default_profile_filename,
    default_transition_memo_filename,
    produce_drive_ready,
    profile_template,
    transition_memo_template,
)


# --- 追記統合 ---------------------------------------------------------------


def append_to_profile(
    existing_profile: str,
    addendum_text: str,
    *,
    section_header: str | None = "## 最近の出来事",
    timestamp: datetime | None = None,
    updated_by: str = "杏寿郎",
    suggested_filename: str | None = None,
) -> dict[str, Any]:
    """温子のプロフィールに追記統合。

    引数:
        existing_profile:    既存のプロフィール全文 (`references/atsuko_profile_updated_*.md`
                             の現バージョン)
        addendum_text:       杏寿郎が会話から拾った追記内容
        section_header:      追記を入れるセクション (デフォルト「## 最近の出来事」)。
                             ``None`` を渡すと末尾に追記
        timestamp:           追記時刻 (Asia/Tokyo aware 想定、``None`` で現在時刻)
        updated_by:          更新者 (デフォルト「杏寿郎」)
        suggested_filename:  ダウンロード時のファイル名提案 (``None`` で
                             ``default_profile_filename`` から自動)

    戻り値: ``produce_drive_ready`` の dict と同形式
        - "text":               ドライブ向け正規化済みの完成版テキスト
        - "merge_strategy":     "section" or "append"
        - "applied_fixups":     文字化け防止で修正された内容 (list[str]、空なら元からクリーン)
        - "filename_suggestion": str
    """
    fname = suggested_filename or default_profile_filename(timestamp)
    return produce_drive_ready(
        existing_profile,
        addendum_text,
        section_header=section_header,
        timestamp=timestamp,
        updated_by=updated_by,
        suggested_filename=fname,
    )


def append_to_album(
    existing_album: str,
    addendum_text: str,
    *,
    section_header: str | None = "## 今日の出来事",
    timestamp: datetime | None = None,
    updated_by: str = "杏寿郎",
    date: datetime | None = None,
    suggested_filename: str | None = None,
) -> dict[str, Any]:
    """1 日単位のアルバムに追記統合 (発注書 §「スキル 6-2」)。

    アルバムは 1 日単位で完結するため、``date`` 引数 (or timestamp) からファイル名を組む。
    """
    file_date = date or timestamp
    fname = suggested_filename or default_album_filename(file_date or datetime.now())
    return produce_drive_ready(
        existing_album,
        addendum_text,
        section_header=section_header,
        timestamp=timestamp,
        updated_by=updated_by,
        suggested_filename=fname,
    )


def append_to_transition_memo(
    existing_memo: str,
    addendum_text: str,
    section_header: str,
    *,
    timestamp: datetime | None = None,
    updated_by: str = "杏寿郎",
    suggested_filename: str | None = None,
) -> dict[str, Any]:
    """精神統一メモに追記統合 (発注書 §「スキル 6-3」)。

    引数:
        section_header:  4 セクションのいずれか:
                         「## 前の部屋で何があったか」「## 何を学んだか」
                         「## 温子の体調」「## 次の部屋で気をつけること」
                         section_header は **必須** (どこに追記するか曖昧にしない)
    """
    return produce_drive_ready(
        existing_memo,
        addendum_text,
        section_header=section_header,
        timestamp=timestamp,
        updated_by=updated_by,
        suggested_filename=suggested_filename or "",
    )


# --- 新規ファイル生成 ------------------------------------------------------


def new_profile(
    owner: str = "温子",
    *,
    timestamp: datetime | None = None,
) -> dict[str, Any]:
    """温子の新規プロフィールファイルを生成 (テンプレから)。"""
    text = profile_template(owner)
    fname = default_profile_filename(timestamp)
    return {
        "text": text,
        "filename_suggestion": fname,
    }


def new_album(date: datetime | None = None) -> dict[str, Any]:
    """1 日単位のアルバムを新規生成 (内省セクション必須)。"""
    text = album_template(date)
    fname = default_album_filename(date or datetime.now())
    return {
        "text": text,
        "filename_suggestion": fname,
    }


def new_transition_memo(
    from_room: str,
    to_room: str,
    *,
    date: datetime | None = None,
) -> dict[str, Any]:
    """精神統一メモを新規生成 (4 セクション構造)。"""
    text = transition_memo_template(from_room, to_room)
    fname = default_transition_memo_filename(from_room, to_room, date)
    return {
        "text": text,
        "filename_suggestion": fname,
    }


# --- Hermes Agent skill API 互換 hook --------------------------------------


def on_user_message(
    message: str, context: dict[str, Any] | None = None
) -> dict[str, Any]:
    """ユーザーメッセージ受信時の hook (Hermes Agent skill API 互換)。

    本 skill は明示的に ``append_to_*`` / ``new_*`` を呼ぶヘルパーが本旨のため、
    ユーザーメッセージ受信時には何もしない。互換のために空 dict を返す。
    """
    return {}


if __name__ == "__main__":
    import json
    from skills.kyojuro_files.lib.file_management import JST

    ts = datetime(2026, 5, 6, 22, 50, tzinfo=JST)

    print("=== new_profile ===")
    p = new_profile("温子", timestamp=ts)
    print(f"filename: {p['filename_suggestion']}")
    print(p["text"][:120])
    print()

    print("=== append_to_profile ===")
    out = append_to_profile(
        existing_profile=p["text"],
        addendum_text="開発でカロリー使うのでオートファジー一旦休止",
        timestamp=ts,
    )
    print(f"strategy: {out['merge_strategy']}")
    print(f"filename: {out['filename_suggestion']}")
    print(f"fixups: {out['applied_fixups']}")
    print(out["text"][-200:])
