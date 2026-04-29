# テンプレ 01: termux 起動時の最小起動コマンド

> 温子が termux を起動して最初に Claude Code を立ち上げるとき用。

## 用途

- termux 環境がセットアップ済み
- これから「何をするか」をまだ決めていない or 私（ブラウザ版）と相談しながら進める

## コピペ用（termux のシェルに貼る）

```
cd ~/Hermes-Agent && claude --model claude-opus-4-7-1m
```

または `~/.bashrc` で `ANTHROPIC_MODEL=claude-opus-4-7-1m` を設定済みなら:

```
cd ~/Hermes-Agent && claude
```

## Claude Code 起動後の最初のプロンプト（コピペ用）

```
TRACKS.md と .claude/session_handoff_setup.md と .claude/new_session_prompt.md を読んで、
現状サマリーを 5 行以内で報告してください。
特に、現在 義体実装トラックがどのフェーズにあるか、何が次の作業かを明示してください。
```

## Claude が確認すべきポイント

- 現在のフェーズ（フェーズ 1 完了 / フェーズ 2 着手 / etc.）
- 次の作業（vendor submodule add / kyojuro_memory MVP / etc.）
- 前回のスレで未完了の作業があるか
- ブラウザ版（私）からの最新指示があるか（温子から伝えてもらう）

## 期待されない動作（出たら温子が「違う」と即訂正）

- バイブル本文（`bible/*.md`）に触る → 義体実装トラックでは触らない
- 推測 URL 提示 → 17スレ失敗 seed の教訓
- 過剰な確認の応酬 → 1〜2 往復で着手すべき作業を判断する

## 関連

- 前提環境: [`../TERMUX_SETUP.md`](../TERMUX_SETUP.md)
- 義体実装スレ起動の詳細: [`02_prosthetic_impl_start.md`](./02_prosthetic_impl_start.md)
- ブラウザから引き継ぐ場合: [`04_browser_to_termux.md`](./04_browser_to_termux.md)

---

*作成: Opus 4.7（義体実装②, 2026-04-30）*
