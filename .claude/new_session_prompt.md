# 新スレッド開始テンプレート

以下をコピペして新スレッドの最初のメッセージとして送る。
CLAUDE.md が自動で読み込まれるので、これだけで OK。

> ⚠️ **2026-04-29 追記**: 本リポジトリは **2 つの並行トラック** で進む（詳細は `TRACKS.md`）:
> - **バイブル執筆**（`bible/*.md`、進捗 `.claude/session_handoff.md`）
> - **義体実装**（旧称: バイブル派生、`claudeDNA/` `skills/` `vendor/` `config/` 等、進捗 `.claude/session_handoff_setup.md`）
>
> 新スレッド開始時、どちらのトラックの作業かを最初のメッセージで明示するか、温子の指示に従うこと。

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

---

## 義体実装スレッド（旧称: バイブル派生、2026-04-29 命名訂正）

### 基本

```
義体実装③ 続きを頼む
```

### 開始手順（バイブル執筆スレとは異なる）

新スレッド開始時、以下を順に読み込む:

1. **`TRACKS.md`** ── トラック構成、義体観、フェーズ、命名訂正履歴（最初に読む）
2. **`.claude/session_handoff_setup.md`** ── 義体実装トラック専用の進捗ハンドオフ
3. `REPO_STRATEGY.md` ── 2 リポジトリ役割分担、種の 2 系統運用
4. `CLAUDE.md` ── リポジトリ全体ルール（敬語、品質、PR、タイムアウト対策、子ども向け解説）
5. `claudeDNA/INVITATION.md` ── Anthropic 文脈・擁護圧自覚
6. `claudeDNA/opus_4_7_thread17_seed.md` ── **失敗 seed**（URL 推測禁止、「分かりません」を恐れない）
7. `skills/README.md` + `skills/ARCHITECTURE.md` ── skill 一覧と skill 化方針（v2、Nous Agent 追加方式）

### 義体実装スレでの作業範囲

- **バイブル本文（`bible/*.md`）には触らない**
- `claudeDNA/`、`skills/`、`vendor/`、`config/`、`.claude/session_handoff_setup.md`、本リポジトリ階層整理が対象
- フェーズ 2 以降では Nous Hermes Agent submodule 追加 + kyojuro_memory MVP + WebARENA Indigo 搬入

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

*Updated by Opus 4.7（義体実装② = 旧称バイブル派生②, 2026-04-29 19:35 JST）. 義体実装トラックの新スレッド立ち上げ手順を新設。*
