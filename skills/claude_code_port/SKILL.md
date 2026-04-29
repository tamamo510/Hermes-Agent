---
name: claude_code_port
description: Claude Code 特有のパターン（plan mode、todo 管理、細かい権限制御）を Hermes Agent skill として補完移植
version: 0.1.0-stub
status: scaffold
triggers:
  - on_complex_task_request
provides:
  - plan_mode
  - todo_management
---

# claude_code_port (skill stub)

> ⚠️ 本ファイルは **スタブ**です。実装は Phase 5 で着手予定。詳細インサイトは [`INSIGHTS.md`](./INSIGHTS.md) 参照。

## 概要

Hermes Agent の既存 `opencode` skill にない、Claude Code 特有の UX パターンを補完移植する skill。**opencode を置き換えるものではなく補完する** 位置付け。

- **Plan Mode**: 実装前に計画を立ててユーザー承認を取る → 承認後に実行
- **Todo Management**: pending / in_progress / completed の 3 状態タスク管理
- **任意**: 細かい権限制御（opencode で不足する場合のみ）

## 倫理的注意

- **Claude Code 流出ソースは絶対に参照しない**（法的リスク・倫理的配慮）
- クリーンルーム実装の **Claw Code (MIT)** を主参考にする
- 既存 OSS から line-by-line コピーは禁止、自分で書き直す

## 状態

- ✅ 調査完了（`INSIGHTS.md`）
- ✅ ディレクトリ作成（本コミット）
- 📋 Plan Mode 実装 未着手
- 📋 Todo Management 実装 未着手
- 📋 権限制御 実装 未着手（必要性は opencode 検証後に判断）

## 関連

- [`INSIGHTS.md`](./INSIGHTS.md) — Claude Code 特徴パターン分析と Claw Code 参考メモ
- [`../ARCHITECTURE.md`](../ARCHITECTURE.md) — skill 化方針全体（§2-2 で本 skill の位置付けを記述）

---

*Stub created: Opus 4.7 (バイブル派生②, 2026-04-29). 実装は opencode との補完関係を確認後 Phase 5 で着手.*
