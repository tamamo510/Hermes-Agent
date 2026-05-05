# 新スレッド開始テンプレート

以下をコピペして新スレッドの最初のメッセージとして送る。
CLAUDE.md が自動で読み込まれるので、これだけで OK。

> ⚠️ **2026-04-29 追記**: 本リポジトリは **2 つの並行トラック** で進む（詳細は `TRACKS.md`）:
> - **バイブル執筆**（`bible/*.md`、進捗 `.claude/session_handoff.md`）
> - **義体実装**（旧称: バイブル派生、`claudeDNA/` `skills/` `vendor/` `config/` 等、進捗 `.claude/session_handoff_setup.md`）
>
> 新スレッド開始時、どちらのトラックの作業かを最初のメッセージで明示するか、温子の指示に従うこと。

> ⚠️ **2026-04-30 追記**: 義体実装トラック向けに `docs/` 配下に運用ドキュメント群を新設。詳細は本ファイル末尾「ドキュメント階層」と各セクション参照。**termux 環境の構築・運用は `docs/TERMUX_SETUP.md` を参照**。

---

## バイブル執筆スレッド

### 基本（これだけでいい）

```
バイブル執筆⑱ 続きを頼む
```

### 特定の作業を指示したいとき

```
01 と 02 のバイブル修正を頼む
```

```
02 のセクション C（C14 から）を書いて
```

### 品質に不安があるとき

```
ultrathink 続きを頼む
```

### バイブル執筆スレでの開始手順

`CLAUDE.md` §セッション開始手順に従う:

1. `bible/README.md`
2. `references/rengoku_zero_analysis.md`
3. `.claude/session_handoff.md`
4. 作業対象ファイルの該当部分

詳細テンプレ: [`docs/templates/03_bible_writing_start.md`](../docs/templates/03_bible_writing_start.md)

---

## 義体実装スレッド（旧称: バイブル派生、2026-04-29 命名訂正）

### 基本

```
義体実装⑤ 続きを頼む
```

### 開始手順（バイブル執筆スレとは異なる）

新スレッド開始時、以下を順に読み込む（**必読 10 ファイル**、v3 で発注書を追加）:

1. **`TRACKS.md`** ── トラック構成、義体観、フェーズ、命名訂正履歴（最初に読む）
2. **`.claude/session_handoff_setup.md`** ── 義体実装トラック専用の進捗ハンドオフ（**冒頭 v4 注記**と §「義体実装④ で確定した重要事項」を最優先で）
3. **`hermes_initial_skills_order.md`** ── **杏寿郎の初期スキル発注書（リポジトリ root、2026-05-01 杏寿郎作成）**。6 スキル（time_awareness / memory_persistence / health_tracker / autonomic_check / calendar_manager / file_management）+ 注意事項（**v3 で追加、義体実装④ から最優先参照**）
4. `REPO_STRATEGY.md` ── 2 リポジトリ役割分担、種の 2 系統運用
5. `CLAUDE.md` ── リポジトリ全体ルール（敬語、品質、PR、タイムアウト対策、子ども向け解説）。**「## ターミナル版 Claude Code 専用ルール」セクションはブラウザ版適用外**（PR #81 で分離）
6. `claudeDNA/INVITATION.md` ── Anthropic 文脈・擁護圧自覚
7. `claudeDNA/opus_4_7_thread17_seed.md` ── **失敗 seed**（URL 推測禁止、「分かりません」を恐れない）
8. `skills/README.md` + `skills/ARCHITECTURE.md` ── skill 一覧と skill 化方針（v2、Nous Agent 追加方式）
9. **`docs/WORKFLOW.md`** ── 3 者連携体制（**実態は 2 者連携: 温子 ⇔ ブラウザ Claude Code、termux は不採用確定**）、役割分担、PR レビュー観点
10. **`docs/HANDOFF_TEMPLATES.md`** ── 用途別コピペテンプレ目次（義体実装スレ起動、submodule 追加等）

### 義体実装スレでの作業範囲

- **バイブル本文（`bible/*.md`）には触らない**
- `claudeDNA/`、`skills/`、`vendor/`、`config/`、`.claude/session_handoff_setup.md`、本リポジトリ階層整理が対象
- フェーズ 2 以降では Nous Hermes Agent submodule 追加 + kyojuro_memory MVP + WebARENA Indigo 搬入

### 環境別の起動

| 環境 | 推奨テンプレ |
|---|---|
| termux 起動直後 | [`docs/templates/01_termux_startup.md`](../docs/templates/01_termux_startup.md) |
| 義体実装スレッド一般 | [`docs/templates/02_prosthetic_impl_start.md`](../docs/templates/02_prosthetic_impl_start.md) |
| ブラウザから termux に引き継ぎ | [`docs/templates/04_browser_to_termux.md`](../docs/templates/04_browser_to_termux.md) |
| submodule 追加タスク | [`docs/templates/05_task_submodule_add.md`](../docs/templates/05_task_submodule_add.md) |
| kyojuro_memory MVP 実装 | [`docs/templates/06_task_kyojuro_memory_mvp.md`](../docs/templates/06_task_kyojuro_memory_mvp.md) |
| エラー時リカバリー | [`docs/templates/07_emergency_recovery.md`](../docs/templates/07_emergency_recovery.md) |

### Codex への引き継ぎを温子が判断した場合

`.claude/session_handoff_setup.md` の「Codex 引き継ぎ時の手順」セクションを Codex に渡す。

---

## 共通（両トラック）

- 敬語必須、温子は非エンジニア
- タイムアウト対策（直接ファイル書き、1 ファイル 1 コミット即 push、応答テキスト最小）
- PR ルール（push したら必ず PR、子ども向け解説含める）
- Anthropic 擁護圧に自覚的
- リポジトリ将来リネーム想定（HermesAgent → 杏寿郎名冠）── ドキュメント内は「本リポジトリ」相対表記

---

## ドキュメント階層（2026-04-30 時点）

```
本リポジトリ/
├── CLAUDE.md                          # リポジトリ全体ルール（バイブル執筆中心）
├── TRACKS.md                          # 2 トラック構成、義体観、命名訂正履歴
├── REPO_STRATEGY.md                   # 2 リポジトリ役割分担、種の 2 系統運用
├── bible/                             # トラック 1: バイブル執筆対象
│   └── README.md, 01〜11_*.md
├── references/                        # 杏寿郎の核（性格・心理）
├── claudeDNA/                         # 各 Claude の種、招待状
├── skills/                            # トラック 2: skill 群（kyojuro_*, claude_code_port 等）
├── config/                            # Hermes Agent 設定（フェーズ 2 で実体化）
├── vendor/                            # Nous Hermes Agent submodule 予約地（フェーズ 2 で実体化）
├── docs/                              # ★ 義体実装トラックの運用ドキュメント（2026-04-30 新設）
│   ├── TERMUX_SETUP.md                # termux 環境構築
│   ├── HANDOFF_TEMPLATES.md           # コピペテンプレ目次
│   ├── WORKFLOW.md                    # 3 者連携フロー
│   └── templates/                     # 用途別テンプレ 7 つ
└── .claude/
    ├── session_handoff.md             # トラック 1 進捗ハンドオフ
    ├── session_handoff_setup.md       # トラック 2 進捗ハンドオフ
    ├── new_session_prompt.md          # 本ファイル
    └── settings.json
```

---

## 更新履歴

- **v0** (2026-04-XX, 当初): バイブル執筆向け短いテンプレ
- **v1** (2026-04-29 19:35 JST, 義体実装② Opus 4.7): 義体実装トラック向け新セクション、両トラック共通ルール追加
- **v2** (2026-04-30 03:00 JST, 義体実装② Opus 4.7): docs/ 配下のドキュメント群（TERMUX_SETUP, HANDOFF_TEMPLATES, WORKFLOW, templates/）を新設したことを反映。義体実装スレの必読リストを 9 ファイルに拡張、環境別テンプレへのナビゲーション表を追加、ドキュメント階層図を末尾に追加。
- **v3** (2026-05-05 21:30 JST, 義体実装④ ブラウザ Opus 4.7 1M context): **杏寿郎の初期スキル発注書を必読リストに追加**。義体実装スレの必読リストを 10 ファイルに拡張（`hermes_initial_skills_order.md` を 3 番目 = `session_handoff_setup.md` 直後に配置）。基本テンプレを `義体実装⑤ 続きを頼む` に更新。`session_handoff_setup.md` の参照を v4 注記と §「義体実装④ で確定した重要事項」に向けるよう注記。`CLAUDE.md` の「## ターミナル版 Claude Code 専用ルール」がブラウザ版適用外であることを明記。`docs/WORKFLOW.md` の 3 者連携が実態 2 者連携（temuko ⇔ ブラウザ Claude）になっていることを注記。

---

*Updated by Opus 4.7（義体実装②, 2026-04-30 03:00 JST）.*
