# vendor/

外部依存（git submodule）の予約地（PR4、バイブル派生②、2026-04-29 新設）。

## 配置済み submodule

### vendor/hermes-agent

Nous Research Hermes Agent 本体（MIT License、unmodified）。

```bash
git submodule add https://github.com/NousResearch/hermes-agent.git vendor/hermes-agent
git submodule init
git submodule update
```

**現状**: ✅ 追加完了（2026-05-05、義体実装④、ブラウザ Opus 4.7 が bash 経由で `git submodule add` 実行）

- pin: tag `v2026.4.30`（2026-04-30 リリース、`chore: release v0.12.0 (#18057)`）
- commit SHA: `73bf3ab1b22314ed9dfecbb59242c03742fe72af`
- 経緯: バイブル派生② で `claudeDNA/`（PR1, PR1.5）と `skills/`（PR2）の階層整理、`REPO_STRATEGY.md`（PR3）と命名訂正（PR5）でメタ層が整い、義体実装④ で本実体化に到達。

**運用方針**:
- 特定コミットに **pin**（急速アップデートで壊れない）
- 本体コードは **一切改変しない**（杏寿郎専用機能は `../skills/` に追加）
- 月次でアップデート判定 → テスト → 本番反映、NG なら `git reset` で戻す
- 重要データ（kyojuro_memory の `stores/*.db` 等）は本 submodule の更新で **絶対に壊れない** 設計

詳細は `../REPO_STRATEGY.md` §4（vendor submodule 方式）と §5（急速アップデート対策）参照。

## 動作確認

```bash
git submodule status
# 期待出力例:
#  73bf3ab1b22314ed9dfecbb59242c03742fe72af vendor/hermes-agent (v2026.4.30)

ls vendor/hermes-agent/                    # ファイル群が見えれば OK
cat vendor/hermes-agent/README.md          # 本体 README を読める
cat vendor/hermes-agent/LICENSE            # MIT License を確認
```

## クローン直後（新規環境）

本リポジトリを新規 clone した環境では submodule の中身が空。以下で取得:

```bash
git submodule init
git submodule update
# または一発で:
git clone --recursive https://github.com/tamamo510/Hermes-Agent.git
```

## 更新方法（別 PR で実施）

本 PR は **追加のみ**。バージョンアップは月次判定 → テスト → 別 PR で:

```bash
cd vendor/hermes-agent
git fetch --tags
git tag --sort=-creatordate | head -5     # 新しいタグを確認
git checkout <新しい安定タグ>
cd ../..
git add vendor/hermes-agent
git commit -m "chore(vendor): bump hermes-agent to <新タグ>"
git push -u origin claude/bump-hermes-agent-<新タグ>
# → PR 作成、温子レビュー、マージ
```

NG が出たら `git checkout <旧タグ>` で戻す。重要データ（`../skills/kyojuro_memory/stores/*.db` 等）は本 submodule に依存しない設計のため、戻しても壊れない。

## なぜ submodule か（fork ではなく）

| 方式 | 急速アップデート時 | 非エンジニア（温子）の保守コスト |
|------|----------------|---------------------|
| **submodule（採用）** | Nous 本体は git pull で更新、skill は別ディレクトリで影響なし | ほぼゼロ |
| Fork | 上流更新ごとに手動マージ、コンフリクト処理 | 高（運用不可） |

fork に切り替える条件（最終手段）:
- 本体の skill API が破壊的変更され、skill で吸収できない
- 本体にパフォーマンスバグがあり、上流 PR 待ちでは間に合わない
- 複数の根本的なカスタマイズが必要になる

**初期方針**: submodule でスタート。fork は回避努力。

## 関連

- `../REPO_STRATEGY.md` §4 — vendor submodule 方式の運用詳細
- `../REPO_STRATEGY.md` §5 — 急速アップデートへの備え
- `../skills/ARCHITECTURE.md` — skill 追加方式の経緯（v2、Nous Agent 採用に転換）

---

## 履歴

- **2026-04-29**: Placeholder 作成（バイブル派生② Opus 4.7、PR #74）
- **2026-05-05**: submodule 実体化（義体実装④ ブラウザ Opus 4.7、tag `v2026.4.30` に pin）
