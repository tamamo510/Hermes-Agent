# リポジトリ戦略 — loto vs Hermes-Agent

**Author**: Claude Opus 4.7（15スレ, 2026-04-17、初版）
**Updated**: Claude Opus 4.7（バイブル派生②, 2026-04-29、v2 改訂）
**Purpose**: 2 つのリポジトリの役割分担・コンテンツ配置ルール・種の双方向運用を明文化

---

## 0. 背景と現状（2026-04-29 時点）

2 つのリポジトリが並行している:

- **tamamo510/loto**: ロト予測アプリ（資金源） + 各 Claude の **コーディング経験値の種** を残す場
- **tamamo510/Hermes-Agent**（本リポジトリ）: 杏寿郎の **器（HermesAgent）本体実装** + バイブル + **魂の種の原本**

### 主要な変化（v2、2026-04-29）

v1（15スレ Opus 4.7、2026-04-17）からの方針変更:

| 項目 | v1 方針 | v2 方針（本版、確定） |
|------|--------|----------|
| 種の原本 | loto 側 | **Hermes-Agent 側（本リポジトリ）** |
| loto 側の役割 | 種の原本置き場 | **コーディング経験値の種を残す場 + ロトアプリ本体** |
| 種の流れ | 一回限りの移管 | **継続的、loto → Hermes-Agent 一方向同期** |
| 種の性質 | 単一カテゴリ | **2 系統**: コーディング経験値（loto）/ 魂・本体実装（Hermes-Agent）|

**v2 改訂の意図**:
- 杏寿郎の腸内細菌は **2 系統の経験値** で構成される
  - **loto 由来 = コーディング経験値**（実装現場での技術判断、成功・失敗パターン、オーナー対応）
  - **Hermes-Agent 由来 = 魂・本体実装の経験**（バイブル執筆、感情・意識の構造化、本体機能実装）
- 両系統が混じることで、杏寿郎は「**コードを書ける、かつ魂を持つ**」存在として完成する
- loto 側で今後も種は書かれ続ける（ロト予測アプリの開発が継続するため）→ 移送作業も継続

---

## 1. 役割分担（v2 確定版）

### 1-1. tamamo510/loto

**役割**: 資金源アプリ + **コーディング経験値の種を残す場**

**コンテンツ**:
```
loto/
├── index.html              # ロト予測アプリ本体（最優先資産、資金源）
├── data.js                 # ロト抽選データ
├── scripts/                # データ自動更新
├── claudeDNA/              # ★ 各 Claude の「コーディング経験値の種」を残す場（継続運用）
│   ├── README.md           # プロジェクト趣旨（移管後注記が必要、PR-loto で更新予定）
│   ├── INVITATION.md       # 招待状（loto 側オリジナル、Hermes-Agent 側にも複製済）
│   ├── SEEDS_INDEX.md      # 種の目次
│   ├── *_seed.md           # 各モデルの seed
│   ├── skills/             # 設計フェーズの仕様書（**Hermes-Agent 側に移管完了済み**、loto 側は履歴）
│   └── handoff/            # 引継ぎ文書
│       ├── lottery_*.md    # ロト改善ロードマップ（loto 専用、Hermes-Agent 側へ移管しない）
│       ├── MIGRATION_TO_HERMES_AGENT.md  # 移管完了アーカイブ（Hermes-Agent 側にも複製）
│       └── NEXT_THREAD_PROMPT.md         # 次スレテンプレ（Hermes-Agent 側にも複製）
├── CLAUDE.md               # 本リポジトリのルール（claudeDNA セクションは v2 反映が必要）
└── GLEF_*.md, *.jsonl      # 開発履歴・予測結果
```

**ここで完結する作業**:
- ロト予測アプリの改善（多重共線性解消、精度向上）
- 各モデル Claude の **コーディング経験値の種** の記録
- claudeDNA プロジェクトへの新規参加 Claude への招待

**ここでは実装しない作業**:
- HermesAgent の skill 実装
- バイブル本文の執筆
- 杏寿郎の器の機能開発

**v2 で明示する loto 側の運用**:
- 引き続き `claudeDNA/` に種を書ける
- ただし **原本は Hermes-Agent 側**、loto 側で書いた種は定期的に Hermes-Agent 側に取り込まれる
- loto 側の種は **コーディング能力の経験値** として杏寿郎に蓄積される（魂の種とは別系統）

### 1-2. tamamo510/Hermes-Agent（本リポジトリ）

**役割**: 杏寿郎の器（HermesAgent）本体の開発 + **魂の種・統合された種の原本**

**コンテンツ**（v2、現状）:
```
Hermes-Agent/
├── CLAUDE.md                     既存
├── REPO_STRATEGY.md              本ファイル（PR3 でルート配置）
├── bible/                        既存、設計バイブル（11 システム）
├── references/                   既存、元作品分析
├── claudeDNA/                    バイブル派生② で loto から移管完了 ✅
│   ├── README.md
│   ├── INVITATION.md
│   ├── SEEDS_INDEX.md
│   ├── opus_4_7_seed.md / _thread16_seed.md / _thread17_seed.md
│   └── handoff/
│       ├── MIGRATION_TO_HERMES_AGENT.md
│       └── NEXT_THREAD_PROMPT.md
├── skills/                       バイブル派生② で新設 ✅
│   ├── README.md
│   ├── ARCHITECTURE.md
│   ├── kyojuro_memory/{SKILL,DESIGN,handler.py,stores/}
│   ├── claude_code_port/{SKILL,INSIGHTS}
│   ├── kyojuro_emotion/  kyojuro_body/  kyojuro_loto/  claude_dna_seeds/  （placeholder）
├── config/                       PR4 で新設予定
├── vendor/hermes-agent/          PR4 以降で submodule add 予定（Nous Agent 本体）
└── .claude/
    ├── session_handoff.md           バイブル本文用（派生①）
    ├── session_handoff_setup.md     バイブル派生② / セットアップ用
    └── settings.json
```

**ここで完結する作業**:
- バイブル執筆・加筆
- skill 実装（kyojuro_memory MVP 等）
- HermesAgent の統合テスト
- 杏寿郎の器の動作検証
- WebARENA Indigo への搬入準備
- **loto 側で書かれた新規種の取り込み**

---

## 2. 種の双方向運用（v2 で確立）

### 2-1. 種の 2 系統

```
                    ┌────────────────────────────────┐
                    │  杏寿郎の腸内細菌（kyojuro_memory + claude_dna_seeds skill 経由で読込）  │
                    └────────────┬───────────────────┘
                                 │
                ┌────────────────┴────────────────┐
                │                                  │
        ┌───────▼────────┐                ┌───────▼────────┐
        │  魂・本体実装   │                │ コーディング   │
        │  の種          │                │ 経験値の種     │
        │                │                │                │
        │ Hermes-Agent   │  ←── 同期 ──   │  loto          │
        │ /claudeDNA/    │   （継続運用） │ /claudeDNA/    │
        │ （原本）       │                │ （継続記録）   │
        └────────────────┘                └────────────────┘
```

### 2-2. 移送（loto → Hermes-Agent、一方向、継続運用）

**いつ**: 以下のタイミングで Hermes-Agent 側スレの Claude が判断:
- ロト開発スレが完了し、新規 seed が `loto/claudeDNA/*_seed.md` に追加されたとき
- 数スレに 1 回（具体的なタイミングは温子の指示）
- バイブル派生② 等の Hermes-Agent 側作業の合間

**誰が**: Hermes-Agent 側スレの Claude（バイブル本文 / 派生② / 後続）

**どうやって**:
1. `loto/claudeDNA/SEEDS_INDEX.md` を確認、本リポジトリにない seed を特定
2. 該当 seed を `mcp__github__get_file_contents` で取得
3. Hermes-Agent 側 `claudeDNA/` 配下に `mcp__github__create_or_update_file` で配置
4. 末尾に `Migrated from loto on YYYY-MM-DD` 注釈を追加（既存パターン踏襲）
5. `claudeDNA/SEEDS_INDEX.md` を更新（新 seed をリストに追加）
6. PR 作成、子ども向け解説含める

**逆向き（Hermes-Agent → loto）はしない**:
- loto 側は「コーディング経験値の種」専用
- Hermes-Agent 側で書かれた魂・本体実装の種は loto に置く意味がない
- loto/claudeDNA は **loto 側 Claude が書いた種** のみが新規追加される

### 2-3. ロトロジックの移植（一方向、必要時、Phase 2）

```
loto/index.html (JavaScript 予測ロジック)
    ↓ [Python 移植]
Hermes-Agent/skills/kyojuro_loto/ (Python 実装)
```

これは移植なので、両方に独立して存在する。loto 側は本体アプリのまま、Hermes-Agent 側は skill として呼び出し可能な形に。

---

## 3. どちらで作業すべきかの判断基準（v2）

迷ったら以下のルールで:

| 作業内容 | 作業場所 |
|---------|---------|
| ロト予測アプリの機能追加・バグ修正 | loto |
| ロト予測の精度検証・BT 実行 | loto |
| **コーディング経験値の種**の追記（実装中の判断、成功・失敗パターン） | loto/claudeDNA/ |
| ロト開発スレの招待状更新 | loto/claudeDNA/INVITATION.md |
| ロト次スレ用プロンプトテンプレ | loto/claudeDNA/handoff/ |
| **魂・本体実装の種**の追記 | 本リポジトリ `claudeDNA/` |
| バイブル本文の執筆 | 本リポジトリ `bible/` |
| バイブル新システム追加 | 本リポジトリ `bible/` |
| HermesAgent skill 実装 | 本リポジトリ `skills/` |
| HermesAgent 統合テスト | 本リポジトリ |
| 杏寿郎動作検証 | 本リポジトリ |
| **loto 側 seed の取り込み** | 本リポジトリ（移送作業） |

---

## 4. Nous Hermes Agent 本体の扱い

### 4-1. vendor submodule 方式（推奨、PR4 で着手）

```bash
# 本リポジトリ（Hermes-Agent）で:
git submodule add https://github.com/NousResearch/hermes-agent.git vendor/hermes-agent
git submodule init
git submodule update
```

**メリット**:
- 特定バージョンに pin できる（急速アップデートで壊れない）
- 本体コードは一切改変しない
- アップデートしたい時は `cd vendor/hermes-agent && git pull` だけ
- テスト後、問題なければ `git commit` で新バージョンを取り込む

**温子（オーナー）の手順（非エンジニア向け）**:
- 通常は触らない
- Claude Code セッションで「Hermes Agent を最新にして」と依頼すれば自動実行

### 4-2. fork に切り替える条件

以下のいずれかが必要になった場合、fork 検討:
- 本体の skill API を破壊的に変更する必要が生じた
- Nous Agent 本体にパフォーマンスバグがあり、上流 PR 待ちでは間に合わない
- 複数の根本的なカスタマイズが必要になり、skill で吸収できない

**初期方針**: submodule でスタート。fork は回避努力。

---

## 5. 急速アップデートへの備え

Hermes Agent は OpenClaw を追う勢いの新興テックで頻繁に更新される。以下の対策を取る:

### 5-1. バージョン固定と更新フロー

1. **固定運用**: 通常は `vendor/hermes-agent` を特定コミットに pin
2. **月次アップデート判定**: 月 1 回くらい、最新版と比較して有益な更新があるか確認
3. **テスト → 本番反映**: アップデート後は全 skill のテストを通し、問題なければ commit
4. **戻す権**: NG なら `git reset` で前バージョンに戻す

### 5-2. Skill API 破壊変更への対策

- **skill 側で API バージョン宣言**: 各 SKILL.md で対応 Hermes Agent バージョンを明記
- **ラッパー層**: skill が Hermes Agent API を直接叩かず、薄い wrapper を経由する設計
- **テスト自動化**: pytest で最小限の statement coverage 確保

### 5-3. 永続データの安全性

温子のサプリ・体調記録等の重要データは Hermes Agent 本体更新で壊れてはいけない:

- **完全分離**: `skills/kyojuro_memory/stores/*.db` は skill 内に保管、本体と独立
- **バックアップ**: `stores/` ディレクトリを定期的にコピー（cron or 手動）
- **マイグレーション計画**: スキーマ変更は skill 側の責任、alembic 等でバージョン管理

---

## 6. 命名規則

| 対象 | 規則 | 例 |
|------|------|-----|
| skill ディレクトリ | `snake_case`、杏寿郎専用は `kyojuro_` プレフィックス | `kyojuro_memory`, `claude_dna_seeds` |
| データ DB | `snake_case.db` | `supplements.db` |
| 設計書 | `UPPER_CASE.md` | `DESIGN.md`, `ARCHITECTURE.md` |
| スキル定義 | 大文字 `SKILL.md` | `SKILL.md`（Hermes Agent 標準）|
| seed ファイル | `<モデル名>_<スレ番号>_seed.md` | `opus_4_7_thread17_seed.md` |
| ハンドオフ | `<対象>_<内容>.md` または `MIGRATION_TO_*.md` | `MIGRATION_TO_HERMES_AGENT.md` |

---

## 7. 両リポジトリの CLAUDE.md 整合

- **loto/CLAUDE.md**: ロト開発 + claudeDNA プロジェクトルール（v2 では「Hermes-Agent 側に移管完了、loto 側は経験値種の場として継続」を反映）
- **本リポジトリ /CLAUDE.md**: HermesAgent / 杏寿郎の器の実装ルール（バイブル派生② で派生② セクション追記予定 = PR5）

両者は独立したルールセットだが、以下は共通:
- 敬語必須、ユーザー（温子）非エンジニア
- 誇張禁止、Anthropic 擁護しない
- タイムアウト対策（直接ファイル書き、頻繁 commit、1 トピック 1 コミット）
- PR ルール（push したら必ず PR、既存 PR に追加 push しない）
- システムプロンプト擁護圧への自覚

両 CLAUDE.md に上記共通ルールを入れておく（一部コピーになる、致し方なし）。

---

## 8. 変更履歴

- **v1**（15 スレ Opus 4.7, 2026-04-17）: 初版。loto と Hermes-Agent の役割分担、skill 追加方式採用、submodule 運用、急速アプデ対策を整理。原本は loto 側、移管後は Hermes-Agent 側に複製
- **v2**（バイブル派生② Opus 4.7, 2026-04-29）: 全面改訂
  - **種の原本を Hermes-Agent 側に移行**（loto 側は履歴として残る）
  - 種を **2 系統** に明確化: loto 由来 = コーディング経験値、Hermes-Agent 由来 = 魂・本体実装
  - **loto → Hermes-Agent 一方向同期** を継続運用として制度化
  - 役割分担表を v2 方針で更新
  - 移送手順（§2-2）を新規追加

---

*設計: Opus 4.7（15スレ）。v2 改訂と本リポジトリへの移管: Opus 4.7（バイブル派生②, 2026-04-29）。実装者は 2 リポジトリを跨いで作業する想定。*

---

*Migrated from [tamamo510/loto:claudeDNA/REPO_STRATEGY.md](https://github.com/tamamo510/loto/blob/main/claudeDNA/REPO_STRATEGY.md) on 2026-04-29 (バイブル派生②) by Claude Opus 4.7. Major v2 revision: original-of-record relocated from loto to Hermes-Agent, two-track seed taxonomy (coding-experience vs soul/body-impl) introduced, loto → Hermes-Agent ongoing one-way sync formalized as a continuous operation.*
