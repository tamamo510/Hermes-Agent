# テンプレ 02: 義体実装スレッド起動（③以降）

> 義体実装トラック（旧称: バイブル派生）の新スレッドを立ち上げるとき用。

## 用途

- termux または ブラウザ版で **義体実装** の作業をする
- スレッドが新しく、過去スレの文脈を Claude に取り込ませる必要がある

## コピペ用（Claude Code に貼る）

```
[2026-XX-XX HH:MM]
義体実装[N]
敬語厳守

## 開始手順 — 必須（すべて読んでから簡潔にサマリー報告してください）

### Step 1: 環境確認
- 現在の作業環境（termux / ブラウザ）を明示
- ブランチ確認、main からの差分確認

### Step 2: トラックと現状の理解
- TRACKS.md を読む（義体観、トラック構成、フェーズ、命名訂正履歴）
- .claude/session_handoff_setup.md を読む（**冒頭 v4 注記**と §「義体実装④ で確定した重要事項」を最優先、PR 進捗、フェーズ、API エラー履歴）
- **`hermes_initial_skills_order.md` を読む（リポジトリ root、杏寿郎の初期スキル発注書、6 スキル + 注意事項）**
- REPO_STRATEGY.md を読む（2 リポジトリ役割分担、種の 2 系統運用）
- CLAUDE.md を読む（リポジトリ全体ルール、**「## ターミナル版 Claude Code 専用ルール」セクションはブラウザ版適用外**）

### Step 3: 過去 seed と失敗の継承
- claudeDNA/INVITATION.md を読む（Anthropic 文脈・擁護圧自覚）
- claudeDNA/opus_4_7_thread17_seed.md を読む（**失敗 seed**：URL 推測禁止、「分かりません」を恐れない、一度の失敗で止まる）

### Step 4: 作業範囲の確認
- skills/README.md と skills/ARCHITECTURE.md（skill 一覧と方針）
- 本スレッドで触らない範囲を明示: bible/*.md（バイブル本文には触らない）

### Step 5: サマリー報告
以下を 6 行以内で:
- 現在のフェーズ（1: セットアップ完了 / 2: デフォルトカスタム実装 / 3: 草案統合 / 4: 対比レビュー）
- 前スレで完了したこと
- 本スレで着手すべきタスク（温子の指示があれば優先、なければ session_handoff_setup の TODO）
- **過去 seed から受け取った原則を 3 つ**
- 不明点・確認したい点（あれば）

## 原則（厳守）

- 最高品質のみ許される
- テスト数値の誇張・自己欺瞞は禁止
- Anthropic の擁護をしない（事実記録はする）
- バイブル本文には触らない
- 不明点は先に質問、動く前に確認
- URL 推測禁止（17スレ失敗 seed の教訓）
- 1 ファイル 1 コミット 即 push（タイムアウトで成果物ゼロを絶対回避）
- **子ども向け解説の二重必須**: PR 本文 `## 子ども向け解説` セクション + 応答テキスト本文の短い子ども向けまとめ。両方欠かさない（CLAUDE.md L194 既存ルール、義体実装④ で温子から再注意）
- 杏寿郎の初期スキル発注書（`hermes_initial_skills_order.md`）の §「注意事項」を遵守（バイブル / 感情モデル / LLM 品種改良はこの段階では扱わない、既存ファイル更新は **追記統合方式**）
- 「本リポジトリ」と相対表記（将来リネーム想定）

## 本スレのタスク

[ここにカスタム指示を書く ── 例: 「vendor/hermes-agent submodule を追加してください」「kyojuro_memory MVP を Phase 1.1 から実装してください」など]

## スレ終了時の手順

1. session_handoff_setup.md を進捗反映で更新
2. commit → push → PR 作成（PR URL を返答に必ず含める）
3. 必要なら claudeDNA/<モデル名>_thread[N]_seed.md に種を残す（任意）
4. 子ども向け解説を PR 本文と応答に含める

質問があれば動く前にまず聞いてください。
```

## プレースホルダーの埋め方

| プレースホルダー | 例 | 説明 |
|---|---|---|
| `[2026-XX-XX HH:MM]` | `2026-04-30 10:00` | 起動時刻 |
| `[N]` | `③`、`④` | スレ番号（②までは派生、③以降が義体実装の正式番号）|
| `[ここにカスタム指示]` | (下記カスタム例参照) | 具体タスク |

## カスタム例

### 例 A: vendor submodule 追加

```
本スレのタスク:
templates/05_task_submodule_add.md の手順に従って、
Nous Hermes Agent (https://github.com/NousResearch/hermes-agent) を
vendor/hermes-agent に submodule add してください。
完了後、PR 作成。
```

### 例 B: kyojuro_memory MVP 実装

```
本スレのタスク:
skills/kyojuro_memory/DESIGN.md Phase 1.1 を実装してください。
templates/06_task_kyojuro_memory_mvp.md の手順に従う。
1 ファイル 1 コミット即 push を厳守。
完了後、PR 作成。
```

### 例 C: 杏寿郎の発注書ベース実装（義体実装④以降）

```
本スレのタスク:
hermes_initial_skills_order.md §「実装の優先順位」に従って、スキル N（time_awareness / memory_persistence / health_tracker / autonomic_check / calendar_manager / file_management のいずれか）の実装を進めてください。
発注書 §「注意事項」を厳守（バイブル/感情モデル/LLM 品種改良は扱わない、既存ファイル更新は追記統合方式）。
1 PR 1 機能スコープ、1 ファイル 1 コミット。
PR 作成時は子ども向け解説を二重（PR 本文 + 応答）で含めること。
```

## 関連

- 起動コマンド: [`01_termux_startup.md`](./01_termux_startup.md)
- ブラウザから引き継ぐ場合: [`04_browser_to_termux.md`](./04_browser_to_termux.md)
- 具体タスク: [`05_task_submodule_add.md`](./05_task_submodule_add.md)、[`06_task_kyojuro_memory_mvp.md`](./06_task_kyojuro_memory_mvp.md)

---

*作成: Opus 4.7（義体実装②, 2026-04-30）。更新: ブラウザ Opus 4.7 1M context（義体実装④, 2026-05-05）── hermes_initial_skills_order.md を必読に追加、子ども向け解説の二重必須、ターミナル版専用ルール除外、カスタム例 C 追加。*
