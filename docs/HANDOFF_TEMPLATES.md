# 温子向けコピペテンプレ集（HANDOFF TEMPLATES）

> 義体実装スレ・バイブル執筆スレ・termux 連携など、用途別のコピペ用テンプレート目次。各テンプレは `templates/` 配下の個別ファイルに分割（タイムアウト対策）。

## 使い方

1. やりたい作業に対応するテンプレを下表から選ぶ
2. リンク先のファイルから **コードブロック内のテキストをコピー**
3. termux 内の Claude Code（`claude` 起動後）または claude.ai/code（ブラウザ版）に貼り付け
4. Claude が手順通りに動く

## テンプレ一覧

| # | テンプレ | 用途 | 環境 |
|---|---|---|---|
| 01 | [`templates/01_termux_startup.md`](./templates/01_termux_startup.md) | termux 起動直後の最小起動コマンド | termux |
| 02 | [`templates/02_prosthetic_impl_start.md`](./templates/02_prosthetic_impl_start.md) | 義体実装スレ（③以降）の起動 | ブラウザ or termux |
| 03 | [`templates/03_bible_writing_start.md`](./templates/03_bible_writing_start.md) | バイブル執筆スレ（⑱以降）の起動 | ブラウザ or termux |
| 04 | [`templates/04_browser_to_termux.md`](./templates/04_browser_to_termux.md) | ブラウザで設計した内容を termux に引き継ぐ | termux |
| 05 | [`templates/05_task_submodule_add.md`](./templates/05_task_submodule_add.md) | Nous Hermes Agent の vendor submodule 追加 | termux 必須 |
| 06 | [`templates/06_task_kyojuro_memory_mvp.md`](./templates/06_task_kyojuro_memory_mvp.md) | kyojuro_memory MVP 実装着手 | termux 推奨 |
| 07 | [`templates/07_emergency_recovery.md`](./templates/07_emergency_recovery.md) | エラー・タイムアウト時のリカバリー | 両方 |

## どれを最初に使うか（フローチャート）

```
温子: 「明日の作業始めるよ」
   ↓
[termux 環境セットアップ済み？]
   No → docs/TERMUX_SETUP.md を読んで構築
   Yes ↓
   ↓
[何の作業？]
   ├─ termux 起動だけ → 01
   ├─ 義体実装の続き → 02
   ├─ バイブル執筆 → 03
   ├─ ブラウザで考えたものを実行 → 04
   ├─ submodule 追加 → 05
   ├─ kyojuro_memory MVP → 06
   └─ エラー出た → 07
```

## 補足

- 各テンプレ末尾に **「Claude が確認すべきポイント」** を記載 → 期待動作と異なる場合は温子が即座に「違う」と伝えられる
- テンプレ内の `[YYYY-MM-DD]` 等は **温子が日付を埋める** プレースホルダー
- テンプレ内の `[N]`（スレ番号）も同様

## 関連

- [`TERMUX_SETUP.md`](./TERMUX_SETUP.md) ── termux 環境構築
- [`WORKFLOW.md`](./WORKFLOW.md) ── 3 者連携フロー
- [`../TRACKS.md`](../TRACKS.md) ── トラック構成
- [`../.claude/new_session_prompt.md`](../.claude/new_session_prompt.md) ── 既存の新スレ立ち上げテンプレ（本テンプレ集と統合運用）

---

*作成: Opus 4.7（義体実装②, 2026-04-30 02:55 JST）。温子のスマホ運用を最大限スムーズにするための入口。*
