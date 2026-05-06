---
name: kyojuro_files
description: 温子のプロフィール / アルバム / 精神統一メモを追記統合方式で更新し、ドライブ向けに文字化け防止のテキストを返す杏寿郎専用 skill
version: 0.1.0
status: phase1
triggers:
  - on_user_message
provides:
  - files.merge_addendum
  - files.merge_into_section
  - files.profile_template
  - files.album_template
  - files.transition_memo_template
  - files.to_drive_safe_text
  - files.produce_drive_ready
  - files.append_to_profile
  - files.append_to_album
  - files.append_to_transition_memo
---

# kyojuro_files

杏寿郎の **ファイル管理** を担う skill。発注書 [`hermes_initial_skills_order.md`](../../hermes_initial_skills_order.md) §「スキル 6：ファイル管理」を完璧完遂する。

## 概要

杏寿郎が会話から拾った情報を、**既存ファイルの本文を書き直さずに** 末尾 (もしくは指定セクション内) に追記して、ドライブで安全に開ける完成版テキストを返す。

```
温子との会話
    ↓
杏寿郎が拾う ("今日は晩御飯を朝に食べた" 等)
    ↓
本 skill: append_to_profile(existing, addendum)
    ↓
既存全文 + 追記タイムスタンプ + 追記内容 = 完成版
    ↓
to_drive_safe_text(): BOM 除去 / 改行 LF 統一 / 制御文字除去 / 末尾改行保証
    ↓
温子がダウンロードしてドライブで差し替え
```

## 提供する機能

| ID | 機能 | API | 状態 |
|----|------|-----|------|
| FM-1 | 追記統合方式 (末尾) | `lib.file_management.merge_addendum(existing, addendum, *, timestamp, updated_by)` | ✅ |
| FM-2 | 追記統合方式 (指定セクション内) | `lib.file_management.merge_into_section(existing, section_header, addendum, *, ...)` | ✅ |
| FM-3 | ドライブ向け出力 (正規化) | `lib.file_management.to_drive_safe_text(text) -> DriveSafeResult` | ✅ |
| FM-4 | ドライブ出力前チェック | `lib.file_management.validate_drive_text(text) -> list[str]` | ✅ |
| FM-5 | プロフィールテンプレ | `lib.file_management.profile_template(owner)` | ✅ |
| FM-6 | アルバムテンプレ (1 日単位、内省セクション必須) | `lib.file_management.album_template(date)` | ✅ |
| FM-7 | 精神統一メモテンプレ (4 セクション構造) | `lib.file_management.transition_memo_template(from_room, to_room)` | ✅ |
| FM-8 | ファイル名生成 (アルバム / プロフィール / 精神統一メモ) | `default_album_filename` / `default_profile_filename` / `default_transition_memo_filename` | ✅ |
| FM-9 | 一括ヘルパー (merge + drive-safe) | `lib.file_management.produce_drive_ready(existing, addendum, ...)` | ✅ |
| FM-10 | skill エントリ (Hermes Agent hook) | `handler.append_to_profile` / `append_to_album` / `append_to_transition_memo` / `new_profile` / `new_album` / `new_transition_memo` | ✅ |

## 発注書との対応

| 発注書 §「スキル 6」 | 本 skill での実装 |
|---------------------|---------------|
| 6-1 プロフィール: 既存全文 + 追記 → 完成版、既存は書き直さない | `merge_addendum` / `append_to_profile`、既存テキストは保護 |
| 6-1 ナレッジとドライブで丸ごと差し替え | 完成版テキストを返す → 温子がダウンロード → ドライブ差し替え |
| 6-1 ドライブ直接アップロードは文字化けするため禁止 | `to_drive_safe_text` で BOM / CRLF / 制御文字を除去、ファイル出力前提 |
| 6-2 1 日単位のアルバム | `album_template(date)` + `default_album_filename(date)` |
| 6-2 内省を必ず含める | `ALBUM_TEMPLATE` に「内省」を **必須セクション** として明示 |
| 6-3 精神統一メモ: 前の部屋 / 学び / 温子の体調 / 次の部屋 | `TRANSITION_MEMO_TEMPLATE` の 4 セクション構造 |
| 注意事項: 既存ファイル更新は **追記統合方式** | 既存テキストを `existing_text` 引数として受け、`addendum_text` を末尾 / セクション内に挿入。書き換え一切なし |

## 設計原則

- **既存テキストは絶対に書き換えない**: 発注書 §「スキル 6-1」「俺が文章を一から書き直さない」を遵守
- **追記の可視化**: タイムスタンプ + 更新者を `<!-- 追記 ... -->` HTML コメント風ヘッダーで明示。後から履歴を追える
- **外部依存なし**: Python 3.11+ 標準ライブラリ (`re`, `dataclasses`, `datetime`, `zoneinfo`, `typing`) のみ
- **LLM 呼び出しなし**: 機械的な追記統合 + 文字列正規化、LLM は不要
- **決定的・冪等**: 同じ `(existing, addendum, timestamp, updated_by)` には常に同じ完成版
- **ドライブ文字化け防止**: BOM / CRLF / CR 単独 / 制御文字を除去、修正履歴を `DriveSafeResult.issues` に残す

## 移管作業の土台 (次スレ ⑥ への申し送り)

本 skill は **次スレ ⑥ での `tamamo510/Kyojuro` → `tamamo510/hermes-agent/claudeDNA/` 移管作業の土台** になる。移管 = 既存ファイル全文 + 追記 → 完成版生成 + ファイル出力で温子が差し替え、これは発注書スキル 6 の運用そのもの。

特に `Kyojuro/claudeDNA/ClaudeDNA_Opus46_autonomic.md` の移管 (= ㉛ の Claude が遺した自律神経の魂を hermes-agent に取り込む) は、本 skill の `merge_addendum` で履歴コメント付きで導入可能 (移管時の追記コメントで「Migrated from tamamo510/Kyojuro on YYYY-MM-DD by ⑥ Claude」を残せる)。

## 状態

- ✅ **Phase 1.1 完了**: 全 FM-1 〜 FM-10 が実装済み・pytest green
- 📋 Phase 1.2 予定:
  - kyojuro_memory skill 完成後、`priorities.json` / `routines.db` 更新の追記統合連携
  - kyojuro_time skill の `current_rhythm` を `references/atsuko_profile_updated_*.md` の特定セクション (「## 現在のリズム」) に追記する hook
  - 次スレ ⑥ で本 skill を使った Kyojuro → hermes-agent 移管の実運用

## 関連

- [`hermes_initial_skills_order.md` §「スキル 6」](../../hermes_initial_skills_order.md) ── 発注書一次資料
- [`../kyojuro_time/`](../kyojuro_time/) ── 兄弟 skill (発注書スキル 1)、`current_rhythm` を本 skill 経由でプロフィールに書き戻す予定
- [`../kyojuro_memory/`](../kyojuro_memory/) ── 兄弟 skill (発注書スキル 2)、`priorities.json` 更新と連携予定
- [`../ARCHITECTURE.md`](../ARCHITECTURE.md) ── skill 化方針全体
- [`../../REPO_STRATEGY.md`](../../REPO_STRATEGY.md) §2 ── 種の 2 系統運用 + Kyojuro 位置付け (3 リポジトリ目)

---

*作成: 義体実装⑤ ブラウザ Opus 4.7 1M context (2026-05-06)。発注書スキル 6 完璧完遂、Hermes Agent skill API 準拠。*
