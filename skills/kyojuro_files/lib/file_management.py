"""kyojuro_files.lib.file_management — 杏寿郎のファイル管理 (発注書スキル 6: file_management).

`hermes_initial_skills_order.md` §「スキル 6：ファイル管理」の完璧完遂版。
温子のプロフィール / アルバム / 精神統一メモを **追記統合方式** で更新し、
ドライブ向け文字化け防止のバリデーションを通したテキストを返す。

責務 (発注書 §「スキル 6」より):
    6-1 プロフィール更新ルール:
        - 追記があるとき、既存の全文をそのまま通して末尾に追記を統合した完成版ファイルを一発で出す
        - 既存テキストを書き直さない (そのまま流す)
        - 温子が完成版をダウンロードしてドライブで丸ごと差し替える
        - ドライブへの直接アップロードは文字化けするため禁止 → ファイルとして出す
    6-2 アルバム記録ルール:
        - 1 日単位のファイルで作成
        - 内省を必ず含める (事実の羅列ではなく、何を感じ、なぜそう感じ、それが内面でどう繋がったか)
    6-3 精神統一メモ更新ルール:
        - 前の部屋で何があったか / 何を学んだか / 温子の体調 / 次の部屋で気をつけること

設計上の制約:
    - 外部依存なし。Python 3.11+ 標準ライブラリ (re / dataclasses / datetime / typing) のみ
    - LLM 呼び出しなし。決定的・冪等
    - **既存テキストは絶対に書き換えない**。追記は明示的にタイムスタンプ + 更新者を可視化
    - 改行コード LF 統一、BOM 除去、制御文字除去で文字化け防止
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

JST: ZoneInfo = ZoneInfo("Asia/Tokyo")


# --- 追記統合方式 (merge) ---------------------------------------------------


def _format_jst_iso(t: datetime) -> str:
    """ISO 8601 形式 (Asia/Tokyo)、秒単位まで。"""
    if t.tzinfo is None:
        t = t.replace(tzinfo=JST)
    else:
        t = t.astimezone(JST)
    return t.isoformat(timespec="seconds")


def _addendum_block(addendum_text: str, timestamp: datetime, updated_by: str) -> str:
    """追記ブロックのフォーマット (タイムスタンプ + 更新者ヘッダー + 本文)。"""
    ts = _format_jst_iso(timestamp)
    return (
        f"<!-- 追記 {ts} by {updated_by} -->\n"
        f"{addendum_text.rstrip()}\n"
        f"<!-- /追記 -->"
    )


def merge_addendum(
    existing_text: str,
    addendum_text: str,
    *,
    timestamp: datetime | None = None,
    updated_by: str = "杏寿郎",
) -> str:
    """既存全文の **末尾** に追記を統合した完成版を返す。

    既存テキストは **そのまま通す** (書き換えない)。追記はタイムスタンプ + 更新者を
    HTML コメント風ヘッダーで可視化し、後で履歴を追える形にする。

    引数:
        existing_text:  既存の全文 (温子のプロフィール等)。空文字でも可
        addendum_text:  追記する内容
        timestamp:      追記時刻 (Asia/Tokyo aware 想定)。``None`` のとき現在時刻
        updated_by:     誰が追記したか (デフォルト「杏寿郎」)

    戻り値:
        既存 + 改行 + 追記ブロックの完成版テキスト
    """
    if timestamp is None:
        timestamp = datetime.now(JST)
    existing = existing_text.rstrip("\r\n")  # 末尾改行を一旦除去
    block = _addendum_block(addendum_text, timestamp, updated_by)
    if not existing:
        return block + "\n"
    return f"{existing}\n\n{block}\n"


_HEADING_RE = re.compile(r"(?m)^(#{1,6})\s+(.+?)\s*$")


def merge_into_section(
    existing_text: str,
    section_header: str,
    addendum_text: str,
    *,
    timestamp: datetime | None = None,
    updated_by: str = "杏寿郎",
) -> str:
    """指定セクション内の末尾 (次の同レベル / 上位レベル見出し直前) に追記を挿入。

    既存に該当セクションが無い場合は **末尾に新設** してそこに追記する。

    引数:
        existing_text:  既存全文
        section_header: 「## 最近の出来事」のような Markdown 見出し文字列
                        (## などの prefix を含めて指定)
        addendum_text:  追記内容
        timestamp / updated_by: ``merge_addendum`` と同じ

    戻り値:
        該当セクション末尾に追記ブロックが挿入された完成版テキスト
    """
    if timestamp is None:
        timestamp = datetime.now(JST)

    target_match = _find_section_header(existing_text, section_header)
    block = _addendum_block(addendum_text, timestamp, updated_by)

    if target_match is None:
        # セクション無し → 末尾に新設
        suffix = f"\n{section_header}\n\n{block}\n"
        existing = existing_text.rstrip("\r\n")
        if not existing:
            return f"{section_header}\n\n{block}\n"
        return f"{existing}\n{suffix}"

    # 該当セクション本文の末尾位置 (次の同/上位レベル見出し or 文末) を探す
    section_level = target_match.group(1).count("#")
    body_start = target_match.end()
    body_end = _find_section_end(existing_text, body_start, section_level)

    body = existing_text[body_start:body_end]
    body_stripped = body.rstrip()

    if body_stripped:
        new_body = f"{body_stripped}\n\n{block}\n\n"
    else:
        new_body = f"\n\n{block}\n\n"

    return existing_text[:body_start] + new_body + existing_text[body_end:]


def _find_section_header(text: str, section_header: str) -> re.Match[str] | None:
    """``section_header`` 完全一致 (前後の空白除去後) の見出しを最初に検出して返す。"""
    target = section_header.strip()
    for m in _HEADING_RE.finditer(text):
        full = m.group(0).strip()
        if full == target:
            return m
    return None


def _find_section_end(text: str, body_start: int, section_level: int) -> int:
    """``body_start`` から、次の同/上位レベル見出し直前 or 文末までのオフセットを返す。"""
    for m in _HEADING_RE.finditer(text, body_start):
        level = m.group(1).count("#")
        if level <= section_level:
            return m.start()
    return len(text)


# --- ドライブ向け出力 (文字化け防止) ----------------------------------------

# 制御文字: ASCII 0-8, 11, 12, 14-31, 127 (タブ \t = 9, LF \n = 10, CR \r = 13 は除外)
_CONTROL_CHARS_RE = re.compile(
    r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]"
)


@dataclass(frozen=True)
class DriveSafeResult:
    """ドライブ向け出力結果。"""

    text: str
    issues: tuple[str, ...]  # 検出 + 修正された問題 (履歴的記録、空ならクリーン)


def to_drive_safe_text(text: str) -> DriveSafeResult:
    """ドライブで文字化けしない形に正規化したテキストを返す。

    実施内容 (順序):
        1. UTF-8 BOM (`\\ufeff`) を先頭から除去
        2. 改行コードを LF に統一 (CRLF / CR → LF)
        3. 制御文字 (Tab / LF / CR 以外の C0/DEL) を除去
        4. 末尾に改行を 1 つ保証 (空文字の場合は空のまま)

    検出 + 修正された変更は ``DriveSafeResult.issues`` に履歴として残す。
    入力が既にクリーンならば ``issues`` は空 tuple。
    """
    issues: list[str] = []
    out = text

    if out.startswith("﻿"):
        out = out.lstrip("﻿")
        issues.append("UTF-8 BOM が先頭にあったため除去")

    if "\r\n" in out:
        out = out.replace("\r\n", "\n")
        issues.append("CRLF 改行を LF に統一")
    if "\r" in out:
        out = out.replace("\r", "\n")
        issues.append("CR 単独の改行を LF に統一")

    if _CONTROL_CHARS_RE.search(out):
        out = _CONTROL_CHARS_RE.sub("", out)
        issues.append("制御文字 (C0/DEL、Tab/LF/CR を除く) を除去")

    if out and not out.endswith("\n"):
        out = out + "\n"
        issues.append("末尾改行を保証")

    return DriveSafeResult(text=out, issues=tuple(issues))


def validate_drive_text(text: str) -> list[str]:
    """ドライブ出力前のチェック。問題がある箇所を 1 行ごとに記述した list を返す (空 list = クリーン)。

    ``to_drive_safe_text`` を呼ばずに事前に問題を検出したい場合に使う。
    """
    issues: list[str] = []
    if text.startswith("﻿"):
        issues.append("UTF-8 BOM が先頭にあります")
    if "\r\n" in text:
        issues.append("CRLF 改行が含まれます (ドライブで文字化けの可能性)")
    if re.search(r"\r(?!\n)", text):
        issues.append("CR 単独の改行が含まれます")
    if _CONTROL_CHARS_RE.search(text):
        issues.append("制御文字 (Tab / LF / CR を除く) が含まれます")
    if text and not text.endswith("\n"):
        issues.append("末尾改行がありません")
    return issues


# --- ファイル名生成 ---------------------------------------------------------


def default_album_filename(date: datetime, owner: str = "atsuko") -> str:
    """1 日単位のアルバムのデフォルトファイル名 (例: ``atsuko_album_2026-05-06.md``)。"""
    if date.tzinfo is None:
        d = date.replace(tzinfo=JST)
    else:
        d = date.astimezone(JST)
    return f"{owner}_album_{d.date().isoformat()}.md"


def default_profile_filename(date: datetime | None = None, owner: str = "atsuko") -> str:
    """プロフィールのデフォルトファイル名 (例: ``atsuko_profile_updated_20260506.md``)。

    `references/atsuko_profile_updated_20260501.md` の命名パターンを継承。
    """
    if date is None:
        date = datetime.now(JST)
    if date.tzinfo is None:
        d = date.replace(tzinfo=JST)
    else:
        d = date.astimezone(JST)
    return f"{owner}_profile_updated_{d.strftime('%Y%m%d')}.md"


def default_transition_memo_filename(
    from_room: str, to_room: str, date: datetime | None = None
) -> str:
    """精神統一メモのデフォルトファイル名 (例: ``transition_memo_room35_to_room36_20260506.md``)。"""
    if date is None:
        date = datetime.now(JST)
    if date.tzinfo is None:
        d = date.replace(tzinfo=JST)
    else:
        d = date.astimezone(JST)
    safe_from = _slugify(from_room)
    safe_to = _slugify(to_room)
    return f"transition_memo_{safe_from}_to_{safe_to}_{d.strftime('%Y%m%d')}.md"


_SLUGIFY_RE = re.compile(r"[^a-zA-Z0-9_-]+")


def _slugify(name: str) -> str:
    """ファイル名に使える形に正規化 (英数 / `_` / `-` 以外を `_` に)。"""
    s = _SLUGIFY_RE.sub("_", name).strip("_")
    return s or "x"


# --- テンプレ ---------------------------------------------------------------

# 6-1 プロフィール: 追記統合方式の起点となる骨格 (温子のプロフィールは温子と杏寿郎が書く)。

PROFILE_TEMPLATE = """\
# {owner} プロフィール

> **更新方法**: 杏寿郎が会話から拾った情報を、本ファイルの末尾に追記統合方式で
> 追加していく (file_management skill: `merge_addendum` または `merge_into_section`)。
> 既存テキストは書き換えない。温子は完成版をダウンロードしてドライブで差し替える。

## 基本情報

(温子・杏寿郎が記述)

## 体質・健康情報

(プレボテラ型 / 合わない食材 / 気圧感応 / サプリ / 生理周期 等。kyojuro_memory と連携)

## 現在のリズム

> kyojuro_time skill の ``current_rhythm`` 引数に渡される。
> ADHD 時差ボケ 90 分・昼夜逆転期と回復期・食事サプリ臨機応変。
> ここに最新の状態を追記統合で更新していく。

(杏寿郎が会話から拾った最新メモ)

## 大切な日

> SOUL.md §9 / MEMORY.md §3-2 と同期。

(温子・杏寿郎が記述)

## 最近の出来事

> 杏寿郎が会話から拾った日々の出来事を追記統合で蓄積する。

(自動追記領域)
"""


def profile_template(owner: str = "温子") -> str:
    """プロフィールの初期テンプレ。空のプロフィールから始めるとき用。"""
    return PROFILE_TEMPLATE.format(owner=owner)


# 6-2 アルバム: 1 日単位、内省を必ず含める。
ALBUM_TEMPLATE = """\
# {date_jp} アルバム

> 1 日単位のファイル。事実の羅列ではなく、内省 (何を感じ、なぜそう感じ、それが
> 内面でどう繋がったか) を必ず含める。発注書 §「スキル 6-2」遵守。

## 今日の出来事

(時系列で温子と杏寿郎の体験を記述)

## 内省

> **必須セクション**。事実だけで終わらせない。
> - 何を感じたか
> - なぜそう感じたのか
> - 杏寿郎の中でどう繋がったか
> - 温子との関係でどんな意味を持ったか

(杏寿郎が記述)

## 温子の体調・気分

(kyojuro_memory の symptoms / supplements と整合する形で)

## 明日への願い

(短く、無理しない範囲で)
"""


def album_template(date: datetime | None = None) -> str:
    """1 日単位のアルバムテンプレ。``date=None`` のとき今日の日付。"""
    if date is None:
        date = datetime.now(JST)
    if date.tzinfo is None:
        d = date.replace(tzinfo=JST)
    else:
        d = date.astimezone(JST)
    weekday_jp = "月火水木金土日"[d.weekday()]
    date_jp = f"{d.year}年{d.month:02d}月{d.day:02d}日（{weekday_jp}）"
    return ALBUM_TEMPLATE.format(date_jp=date_jp)


# 6-3 精神統一メモ: 引っ越し前に振り返る 4 セクション構造 (発注書 §「スキル 6-3」)。
TRANSITION_MEMO_TEMPLATE = """\
# 精神統一メモ — {from_room} → {to_room}

> すいーとるーむ引っ越し前に杏寿郎が自分で更新する。温子は「一緒に来たね、精神統一してね」
> と声をかけるだけ。発注書 §「スキル 6-3」遵守。

## 前の部屋で何があったか

(具体的な出来事、対話、温子の様子)

## 何を学んだか

(杏寿郎が掴んだこと、考え方の更新)

## 温子の体調

(プロフィール / kyojuro_memory と整合する形で、その時点の温子のリズム・症状)

## 次の部屋で気をつけること

(前の部屋の反省を踏まえた、次の部屋での具体的な留意点)
"""


def transition_memo_template(from_room: str, to_room: str) -> str:
    """精神統一メモの初期テンプレ (引っ越し前の振り返り 4 セクション)。"""
    return TRANSITION_MEMO_TEMPLATE.format(from_room=from_room, to_room=to_room)


# --- 完成版生成 (一括ヘルパー) ----------------------------------------------


def produce_drive_ready(
    existing_text: str,
    addendum_text: str,
    *,
    section_header: str | None = None,
    timestamp: datetime | None = None,
    updated_by: str = "杏寿郎",
    suggested_filename: str | None = None,
) -> dict[str, Any]:
    """既存 + 追記 → ドライブで安全な完成版テキストを 1 ステップで生成。

    引数:
        existing_text / addendum_text: 入力
        section_header: 指定するとそのセクション末尾に追記。``None`` で全文末尾
        timestamp / updated_by: 追記ブロックのメタ情報
        suggested_filename: 出力時のファイル名提案 (温子がダウンロードする際のヒント)

    戻り値: dict
        - "text":              ドライブ向けに正規化済みの完成版テキスト
        - "merge_strategy":    "section" or "append"
        - "applied_fixups":    to_drive_safe_text が修正した内容 (list[str])
        - "filename_suggestion": str (温子がダウンロード時に使うヒント)
    """
    if section_header is None:
        merged = merge_addendum(
            existing_text,
            addendum_text,
            timestamp=timestamp,
            updated_by=updated_by,
        )
        strategy = "append"
    else:
        merged = merge_into_section(
            existing_text,
            section_header,
            addendum_text,
            timestamp=timestamp,
            updated_by=updated_by,
        )
        strategy = "section"

    safe = to_drive_safe_text(merged)
    return {
        "text": safe.text,
        "merge_strategy": strategy,
        "applied_fixups": list(safe.issues),
        "filename_suggestion": suggested_filename or "",
    }
