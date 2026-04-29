# テンプレ 05: vendor/hermes-agent submodule 追加タスク

> Nous Research Hermes Agent 本体を vendor/hermes-agent に submodule として追加する具体タスク。
>
> ⚠️ **termux 必須**（GitHub MCP では submodule add が不可）。

## 用途

- 義体実装のフェーズ 2 開始時に **最初にやる作業**
- vendor/ ディレクトリの placeholder（PR4 で配置）を実体化する

## 前提

- termux 環境セットアップ済み（[`../TERMUX_SETUP.md`](../TERMUX_SETUP.md)）
- `cd ~/Hermes-Agent` 済み
- main から最新 pull 済み（`git pull origin main`）

## コピペ用テンプレ（Claude Code に貼る）

```
[2026-XX-XX HH:MM] 義体実装[N] - vendor/hermes-agent submodule add
敬語厳守

## 文脈

vendor/ ディレクトリは PR4（バイブル派生②, 2026-04-29）で placeholder（README.md のみ）として作成済み。
本タスクで Nous Research Hermes Agent 本体を submodule として追加し、フェーズ 2（デフォルトカスタム実装）の土台を作る。

## 開始手順

1. TRACKS.md を読む（特にフェーズ 2 の意図）
2. REPO_STRATEGY.md §4「Nous Hermes Agent 本体の扱い」を読む（submodule 方式採用の理由）
3. vendor/README.md を読む（既存の運用方針メモ）

## 実装手順

1. 最新 main から新ブランチを切る:
   git fetch origin
   git checkout -b claude/add-hermes-agent-submodule origin/main

2. submodule を追加:
   git submodule add https://github.com/NousResearch/hermes-agent.git vendor/hermes-agent
   git submodule init
   git submodule update

3. **追加された commit SHA を確認**し、それに pin（不要な追従を避ける）:
   cd vendor/hermes-agent
   git log -5 --oneline    # 最新数件のコミットを確認
   git checkout <安定そうなコミット SHA>
   cd ../..
   git add vendor/hermes-agent

4. .gitmodules ファイルが正しく作成されていることを確認:
   cat .gitmodules

5. vendor/README.md を「submodule 追加完了」状態に更新:
   - 「未追加」→「追加完了（YYYY-MM-DD、commit <SHA>）」
   - 動作確認手順を追記
   - submodule 更新方法を追記

6. commit + push + PR

## 制約・原則

- 本体（vendor/hermes-agent）には**改変を加えない**
- 杏寿郎専用機能は skills/ に追加（vendor/ には触らない）
- submodule の更新は別 PR で対応（本 PR は追加のみ）
- 1 commit 1 push
- 子ども向け解説を PR 本文に含める
- 「本リポジトリ」相対表記（将来リネーム想定）

## ブランチ名

claude/add-hermes-agent-submodule

## PR タイトル / 本文

タイトル: feat(vendor): add Nous Hermes Agent as git submodule (Phase 2 foundation)

本文要素:
- Summary（submodule 追加の意義、フェーズ 2 の土台）
- 追加された commit SHA、サブモジュール path
- vendor/README.md 更新内容
- Test plan（git submodule status で確認、vendor/hermes-agent 内のファイル群が読めるか確認）
- 子ども向け解説（杏寿郎の体に骨格・神経系の幹が入った）

## 完了時の報告

- PR URL を温子に報告
- 温子がブラウザの私に貼ってレビュー依頼

## トラブルシューティング

| 症状 | 対処 |
|----|----|
| submodule add が拒否される | vendor/ 内に既存ファイル（README.md placeholder）があると衝突。一時退避するか `git rm --cached vendor/README.md` してから add |
| Permission denied (publickey) | https URL を使う（SSH ではなく）|
| submodule 更新が反映されない | git submodule update --init --recursive で再初期化 |
| Nous Research の最新 main が壊れている | 安定そうなタグやコミット（リリースタグ等）に pin して回避 |

## 質問があれば動く前に聞いてください
```

## 関連

- 義体実装スレ起動: [`02_prosthetic_impl_start.md`](./02_prosthetic_impl_start.md)
- 次のタスク: [`06_task_kyojuro_memory_mvp.md`](./06_task_kyojuro_memory_mvp.md)
- 設計根拠: [`../../REPO_STRATEGY.md`](../../REPO_STRATEGY.md) §4
- vendor/ placeholder: [`../../vendor/README.md`](../../vendor/README.md)

---

*作成: Opus 4.7（義体実装②, 2026-04-30）*
