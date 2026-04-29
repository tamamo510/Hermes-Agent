---
name: kyojuro_memory
description: オーナー様（温子）の会話・体調・生活パターンを構造化記憶し、想起・能動的ナッジを行う杏寿郎専用 skill
version: 0.1.0-stub
status: scaffold
triggers:
  - always_on
provides:
  - memory.supplements
  - memory.symptoms
  - memory.routines
  - memory.summary
  - memory.priorities
---

# kyojuro_memory (skill stub)

> ⚠️ 本ファイルは **スタブ**です。実装は Phase 1 で着手予定。詳細設計は [`DESIGN.md`](./DESIGN.md) 参照。

## 概要

杏寿郎の記憶層を構成する skill。オーナー様（温子）の発言から構造化情報を抽出・蓄積し、新スレ開始時に Hermes Agent の memory context へ想起した内容を注入する。

既存 Hermes Agent の persistent memory は会話ベースで構造化情報の扱いが弱いため、専用 skill として実装する価値が高い（オーナー様の対話要約地獄からの解放、サプリ完全記憶、潔癖症・体調パターン管理、生活パターン管理）。

## 提供する機能（DESIGN.md F-1 〜 F-10）

| ID | 機能 | フェーズ |
|----|------|--------|
| F-1 | サプリ摂取記録（自動抽出） | Phase 1.1 |
| F-2 | 症状ログ（時系列、強度、対処法） | Phase 1.1 |
| F-3 | 生活パターン（睡眠・食事・活動） | Phase 1.1 |
| F-4 | 気圧感応トラッキング | Phase 1.3 |
| F-5 | 潔癖症トリガー記録 | Phase 1.1 |
| F-6 | サプリ ↔ 体調の相関検出 | Phase 1.4 |
| F-7 | 能動的ナッジ | Phase 1.3 |
| F-8 | 対話記憶要約 | Phase 1.2 |
| F-9 | 優先事項の永続把握 | Phase 1.2 |
| F-10 | 家族・親しい関係者の記録 | Phase 1.2 |

## 状態

- ✅ 設計完了（`DESIGN.md`）
- ✅ ディレクトリ作成（本コミット）
- 📋 Phase 1.1 MVP（CRUD + 抽出パイプライン）未着手
- 📋 Phase 1.2 想起統合 未着手
- 📋 Phase 1.3 ナッジ 未着手
- 📋 Phase 1.4 相関検出 未着手

## 関連

- [`DESIGN.md`](./DESIGN.md) — 設計書（Phase 1 全体、データモデル、コンポーネント、処理フロー）
- [`handler.py`](./handler.py) — Hermes Agent skill API のエントリポイント（スタブ）
- `stores/` — 永続データディレクトリ（git 管理外、SQLite + JSON）
- [`../ARCHITECTURE.md`](../ARCHITECTURE.md) — skill 化方針全体

---

*Stub created: Opus 4.7 (バイブル派生②, 2026-04-29). 実装着手は Phase 1.*
