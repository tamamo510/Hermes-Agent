# テンプレ 06: kyojuro_memory MVP 実装タスク（Phase 1.1）

> kyojuro_memory skill の Phase 1.1 MVP（最小機能）を実装する。
>
> ⚠️ **termux 推奨**（複数ファイル連続コミット、SQLite 操作、pytest 実行など、ローカル環境が便利）。

## 用途

- skills/kyojuro_memory/DESIGN.md Phase 1.1 を実装
- 5/10 までに最低限動く状態を作る（杏寿郎の記憶層 MVP）

## 前提

- vendor/hermes-agent submodule 追加済み（テンプレ 05 完了）
- `skills/kyojuro_memory/` に SKILL.md, DESIGN.md, handler.py（スタブ）, stores/.gitkeep が存在

## コピペ用テンプレ（Claude Code に貼る）

```
[2026-XX-XX HH:MM] 義体実装[N] - kyojuro_memory MVP (Phase 1.1)
敬語厳守

## 文脈

skills/kyojuro_memory/DESIGN.md Phase 1.1 の MVP を実装する。
温子の対話要約地獄からの解放、サプリ完全記憶、症状時系列、生活パターン管理が目的。
データは SQLite + JSON、すべてローカル保存。

## 開始手順

1. skills/kyojuro_memory/DESIGN.md を熟読（特に §1 要件、§2 データモデル、§3 コンポーネント、§4 処理フロー、§6 Phase 1.1）
2. skills/kyojuro_memory/SKILL.md を確認（Hermes Agent skill API）
3. skills/kyojuro_memory/handler.py のスタブを確認（hook 4 つ）
4. vendor/hermes-agent/skills/autonomous-ai-agents/opencode/ を参考に skill API パターンを把握

## 実装手順（Phase 1.1 MVP）

### Step 1: ストア層実装（独立、単体テスト容易）

1. skills/kyojuro_memory/lib/__init__.py 作成
2. skills/kyojuro_memory/lib/stores/__init__.py 作成
3. skills/kyojuro_memory/lib/stores/supplement_store.py 実装（CRUD）
4. skills/kyojuro_memory/lib/stores/symptom_store.py 実装（CRUD）
5. skills/kyojuro_memory/lib/stores/routine_store.py 実装（CRUD）

各ストアは DESIGN.md §2-2 のスキーマに完全準拠。各 1 ファイル 1 commit 即 push。

### Step 2: 抽出プロンプトテンプレ

1. skills/kyojuro_memory/lib/extractors/__init__.py 作成
2. skills/kyojuro_memory/lib/extractors/supplement_extractor.py 実装
3. skills/kyojuro_memory/lib/extractors/symptom_extractor.py 実装
4. skills/kyojuro_memory/lib/extractors/routine_extractor.py 実装

各抽出器は DESIGN.md §4-1 の EXTRACTION_PROMPT パターンに準拠。

### Step 3: handler.py の on_user_message 実装

スタブの NotImplementedError を外し、以下を実装:
- 入力 message に対して 3 つの extractor を並列実行
- 抽出結果を各 store に保存
- 返り値: 抽出件数のサマリー dict

### Step 4: pytest 最小限

1. skills/kyojuro_memory/tests/__init__.py 作成
2. skills/kyojuro_memory/tests/test_stores.py 実装（CRUD テスト）
3. skills/kyojuro_memory/tests/test_extractors.py 実装（モック LLM での抽出テスト）
4. skills/kyojuro_memory/tests/test_handler.py 実装（on_user_message 統合テスト）

## 制約・原則

- データリーク禁止（テストデータが本番 stores/ に書き込まれない）
- プライバシー絶対（外部送信なし、全データローカル）
- 1 ファイル 1 コミット即 push（タイムアウト対策）
- バイブル本文には触らない
- Anthropic フィルターで「過剰」「設計負荷」感覚が出たら警戒（杏寿郎の核機能なので妥協しない）
- 子ども向け解説を PR 本文に含める（kyojuro_memory = 海馬、というたとえ）
- 「本リポジトリ」相対表記

## ブランチ名

claude/kyojuro-memory-mvp-phase-1-1

## PR タイトル / 本文

タイトル: feat(skills/kyojuro_memory): implement Phase 1.1 MVP (stores + extractors + handler)

本文要素:
- Summary（Phase 1.1 の意義、サプリ・症状・生活ログの基本 CRUD + 抽出）
- 実装したファイル一覧
- DESIGN.md とのマッピング
- pytest 結果（成功テスト数）
- 子ども向け解説（杏寿郎の海馬の最小機能ができた、温子のお薬や体調を覚えてくれる）

## 完了時の報告

- PR URL を温子に報告
- 温子がブラウザの私に貼ってレビュー依頼
- レビュー後、Phase 1.2（想起統合）に進むかを温子と相談

## 質問があれば動く前に聞いてください

特に:
- LLM 呼び出し方式（Hermes 405B エンドポイント、API キー、フォールバック）
- pytest 環境（Python 3.11+ 必須、依存パッケージは pip install）
- stores/ ディレクトリの .gitignore 設定（*.db を除外する想定で OK か）
```

## 補足: PR の分割推奨

タイムアウト対策として、Phase 1.1 を **3〜4 PR に分割** することを推奨:

| PR | スコープ | ファイル数目安 |
|---|---|---|
| 6.1 | ストア層（supplement / symptom / routine の 3 store + lib/__init__）| 5 |
| 6.2 | 抽出プロンプトテンプレ（3 extractor + lib/extractors/__init__）| 4 |
| 6.3 | handler.py 実装 + 統合テスト | 1-2 |
| 6.4 | pytest テスト群（3 test ファイル + tests/__init__）| 4 |

各 PR で温子のマージ → ブラウザ私のレビューを挟むことで、品質担保。

## 関連

- 設計書: [`../../skills/kyojuro_memory/DESIGN.md`](../../skills/kyojuro_memory/DESIGN.md)
- skill 定義: [`../../skills/kyojuro_memory/SKILL.md`](../../skills/kyojuro_memory/SKILL.md)
- handler スタブ: [`../../skills/kyojuro_memory/handler.py`](../../skills/kyojuro_memory/handler.py)
- 前提タスク: [`05_task_submodule_add.md`](./05_task_submodule_add.md)
- 義体実装スレ起動: [`02_prosthetic_impl_start.md`](./02_prosthetic_impl_start.md)

---

*作成: Opus 4.7（義体実装②, 2026-04-30）*
