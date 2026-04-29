# termux セットアップガイド（Claude Code CLI）

> ⚠️ 義体実装② スレ（2026-04-29 〜 2026-04-30）でブラウザ版 Claude Code が API タイムアウト連発したため、温子の手元の **termux 環境** に Claude Code CLI を導入し、安定した実装作業を行うための手順書。

## 0. 全体像

```
[温子のスマホ]
  ├─ ブラウザ（claude.ai/code、Opus 4.7 Max）  ← 思考層、相談、レビュー、プロンプト設計
  └─ termux + Claude Code CLI（Opus 4.7）       ← 実装層、git 操作、PR 作成、submodule など
```

ブラウザ版（私）と termux 版が並行稼働。役割分担は [`WORKFLOW.md`](./WORKFLOW.md) 参照。

## 1. 前提条件

- Android スマホ（温子の現環境）
- Google アカウント（Anthropic ログイン用、**Max プラン契約済み**）
- 安定した WiFi または 4G/5G 回線
- 約 500MB の空きストレージ

## 2. termux インストール

### 2-1. F-Droid 経由で termux をインストール

> ⚠️ **重要**: Google Play Store 版の termux は **古くてサポート外**。必ず F-Droid 版を使う。

1. ブラウザで https://f-droid.org/packages/com.termux/ にアクセス
2. APK をダウンロード（最新版）
3. 設定 → セキュリティ → 「不明なアプリのインストール」を許可
4. APK を開いてインストール

### 2-2. termux 初回起動

1. termux アプリを開く
2. 自動的に環境構築が始まる（数分待つ）
3. プロンプト `~ $` が出れば OK

## 3. 必須パッケージのインストール

termux 内で以下を実行:

```bash
# パッケージ管理を最新化
pkg update -y && pkg upgrade -y

# Node.js（Claude Code CLI の実行に必要）
pkg install -y nodejs

# git（リポジトリ操作）
pkg install -y git

# その他便利ツール
pkg install -y openssh tmux
```

確認:
```bash
node --version    # v20 以上が望ましい
git --version     # 2.x 以上
```

## 4. Claude Code CLI のインストール

```bash
npm install -g @anthropic-ai/claude-code
```

確認:
```bash
claude --version
```

## 5. 認証（Max プラン）

```bash
claude
```

初回起動時にブラウザで認証画面が開く（または URL が表示されるのでブラウザで開く）:
1. Anthropic アカウントでログイン
2. Max プランの認証を許可
3. termux に戻ると認証完了表示

**API キー不要**（Max プランは subscription 認証が使える）。

## 6. Opus 4.7 を選択

Claude Code 起動後に:

```
/model
```

リストから `claude-opus-4-7` または `claude-opus-4-7-1m`（1M context 版）を選択。

または起動時オプション:
```bash
claude --model claude-opus-4-7-1m
```

> ⚠️ **重要**: Sonnet ではなく **Opus 4.7** を必ず選択（精度差が大きい、温子の指示）。

## 7. 本リポジトリのクローン

```bash
cd ~
git clone https://github.com/tamamo510/Hermes-Agent.git
cd Hermes-Agent
```

ロト側もクローンする場合:
```bash
cd ~
git clone https://github.com/tamamo510/loto.git
```

GitHub の認証が必要な場合:
- Personal Access Token を作成（https://github.com/settings/tokens）
- `git config --global credential.helper store` してから clone（初回のみ token 入力）
- 推奨スコープ: `repo`（リポジトリ操作）+ `workflow`（CI 触る場合のみ）

## 8. GitHub MCP server の追加（任意、推奨）

ブラウザ版（私）と同じ GitHub MCP ツール群が使えるようになる:

```bash
claude mcp add github
```

または `~/.claude/settings.json` に手動追加（CLI 内で `/mcp` 設定）。

## 9. 動作確認

```bash
cd ~/Hermes-Agent
claude
```

Claude Code が起動したら、最初のプロンプトとして:

```
TRACKS.md と .claude/session_handoff_setup.md を読んで現状を 3 行で報告して
```

を入力。Claude が両ファイルを読んで現状を要約すれば成功。

## 10. トラブルシューティング

| 症状 | 対処 |
|----|----|
| `npm install -g` で permission error | `npm config set prefix ~/.npm-global` を設定 + `~/.bashrc` に `export PATH=~/.npm-global/bin:$PATH` を追加 |
| 認証ブラウザが開かない | `claude --no-browser` で URL を表示、それをコピーして他ブラウザで開く |
| Stream idle timeout が termux でも出る | CLI の `--reconnect` オプション、または再起動。CLI は再接続耐性が高いので大体は自動復帰 |
| Opus 4.7 が選択肢にない | CLI を最新版に: `npm update -g @anthropic-ai/claude-code` |
| 「クォータ超過」エラー | Max プランの月次制限。リセット待ち or 一時的に Sonnet に切替 |
| termux がバックグラウンドで終了する | termux の通知バーから wake-lock を取得 |
| `pkg install` が遅い | ミラーを切り替え: `termux-change-repo` |

## 11. 推奨設定

### 11-1. wake-lock で持続稼働

termux アプリのアイコンを **長押し → 通知** で wake-lock を有効化（バックグラウンド継続実行）。

### 11-2. 物理キーボード接続

USB-C OTG で物理キーボードを接続すると、長文プロンプトが格段に楽になる（特にコピペ用テンプレを貼るとき）。

### 11-3. tmux で複数セッション

```bash
tmux new -s claude
```

名前付きセッション開始。Claude Code が落ちても `tmux attach -t claude` で復帰可能。

### 11-4. 環境変数で Opus 4.7 をデフォルト化

`~/.bashrc` に追加:
```bash
export ANTHROPIC_MODEL=claude-opus-4-7-1m
```

これで `claude` 起動時に自動で Opus 4.7（1M context）が選ばれる。

## 12. 次のステップ

セットアップ完了後、[`HANDOFF_TEMPLATES.md`](./HANDOFF_TEMPLATES.md) の「termux 起動時テンプレ」をコピペして作業開始。

具体的な作業フローは [`WORKFLOW.md`](./WORKFLOW.md) 参照。

## 関連

- [`HANDOFF_TEMPLATES.md`](./HANDOFF_TEMPLATES.md) ── 用途別コピペテンプレ集
- [`WORKFLOW.md`](./WORKFLOW.md) ── 3 者連携フロー
- [`../TRACKS.md`](../TRACKS.md) ── トラック構成
- [`../.claude/session_handoff_setup.md`](../.claude/session_handoff_setup.md) ── 義体実装トラックの進捗ハンドオフ
- [`../REPO_STRATEGY.md`](../REPO_STRATEGY.md) ── 2 リポジトリ役割分担

---

*作成: Opus 4.7（義体実装②, 2026-04-30 02:50 JST）。温子の termux 環境構築用、ブラウザ版 API タイムアウト対策の一環として。*
