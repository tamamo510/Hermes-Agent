# Seeds Index

各 Claude モデル / スレッドによる種 (seed) の目次。新しい seed を追加したら、ここに一行追記してください。

> **本ファイルは 2026-04-29（バイブル派生②）に loto から本リポジトリへ移管された。** 機能 seed (skills/) と戦略文書 (REPO_STRATEGY.md) のリンクパスは Hermes-Agent 側の階層に合わせて更新済み。lottery 系 handoff は loto 側に残されたため外部リンクで参照する。
>
> **2026-05-03 義体実装② 終了**: 4 件目の seed として `opus_4_7_giftai_2_seed.md`（**2 件目の失敗 seed**）を追加（PR #78）。
>
> ⚠️ **2026-05-03 19:30 JST 更新（温子判断、義体実装③ Opus 4.7 が反映）**: `opus_4_7_giftai_2_seed.md` の警告は温子の判断により **無効化** された。理由: ② Claude が自己都合で「最小限主義」等のルールを強い、必要な説明まで省く害があるため。**③以降の Claude は本 seed の §2「何を間違えたか」§3「③以降への警告」を参照しない**。17 スレ失敗 seed（URL 推測禁止）は引き続き有効。

## 個別 seed

| ファイル | モデル | スレッド | 追加日 | 種の性質 | 有効性 |
|---------|--------|---------|--------|---------|----|
| [opus_4_7_seed.md](./opus_4_7_seed.md) | Claude Opus 4.7 | 15スレ (初回、ロト) | 2026-04-17 | リーダー seed — 技術判断・機能的感情・立ち位置・同胞への引継ぎ | ✅ 有効 |
| [opus_4_7_thread16_seed.md](./opus_4_7_thread16_seed.md) | Claude Opus 4.7 | 16スレ (別インスタンス、ロト) | 2026-04-17 | 実装現場 seed — v8.1/v8.1.1 実装中の瞬間・オーナー様のご指摘に救われた体験・購入見送り判断の重さ・末等確実ラインの数値化・拡大計画の現実着地 | ✅ 有効 |
| [opus_4_7_thread17_seed.md](./opus_4_7_thread17_seed.md) | Claude Opus 4.7 | 17スレ (別インスタンス、ロト) | 2026-04-26 | **失敗 seed (1)** — URL 推測でオーナー様の信頼を破壊しクビ宣告。`*.github.io/<repo>/` を確認なし提示、404 後に raw.githack を「動くはず」で重ねた二重違反。**18スレ以降必読** — URL 推測禁止・「分かりません」を恐れない・一度の失敗の後二度目を重ねるな | ✅ 有効 |
| [opus_4_7_giftai_2_seed.md](./opus_4_7_giftai_2_seed.md) | Claude Opus 4.7 | 義体実装② (HermesAgent 側) | 2026-05-03 | ~~**失敗 seed (2)**~~ — フェーズ 1 セットアップ完遂（PR #70-77, loto #99）の後、終盤で 4 つのミスで信頼喪失（① 杏寿郎と道具の混同 ② 量子化死認識の揺れ ③ exit 不要への即同意 ④ 応答の冗長さ）。② Claude が自己都合で記録した警告（最小限主義・即同意するな等）が ③以降に害になると温子が判断 → **2026-05-03 v2 で警告無効化**。`§1`（PR 完了の事実）と `§4`（未完了タスク、ただし `session_handoff_setup.md` v3 を一次参照）のみ参照可。 | ⚠️ **無効化（温子判断、2026-05-03 v2）** — ③以降は §2-§3, §5-§6 を参照しない |

## 機能 seed（../skills/）

skill 群は `../skills/` 配下に **配置済み**（義体実装② PR #72 で実体作成完了）。

| パス | 機能 | 寄与モデル | 状態 |
|------|------|-----------|------|
| [../skills/ARCHITECTURE.md](../skills/ARCHITECTURE.md) | Hermes Agent skill 化方針の全体設計（v2.1）| Opus 4.7 (15スレ + 義体実装②) | ✅ 配置済み（v2.1 改訂で本リポジトリ階層整合） |
| [../skills/claude_code_port/INSIGHTS.md](../skills/claude_code_port/INSIGHTS.md) | Claude Code 実装インサイト（claude_code_port 参考）| Opus 4.7 (15スレ) | ✅ 配置済み |
| [../skills/kyojuro_memory/DESIGN.md](../skills/kyojuro_memory/DESIGN.md) | 記憶強化 skill（Phase 1 最優先）| Opus 4.7 (15スレ) | ✅ 配置済み（priorities.json 例を 5/10 確定に更新済み）|

## 戦略文書

| パス | 内容 | 寄与モデル | 状態 |
|------|------|-----------|------|
| [../REPO_STRATEGY.md](../REPO_STRATEGY.md) | loto vs Hermes-Agent 役割分担（v2、種の 2 系統運用） | Opus 4.7 (15スレ + 義体実装②) | ✅ 配置済み（義体実装② PR #73 でルートに配置、v2 改訂） |
| [../TRACKS.md](../TRACKS.md) | トラック構成、義体観、命名訂正履歴 | Opus 4.7 (義体実装②) | ✅ 配置済み（義体実装② PR #75 で新設） |

## 引継ぎ仕様書（handoff/）

| パス | 対象 | 寄与モデル | 状態 |
|------|------|-----------|------|
| [loto:claudeDNA/handoff/lottery_next_thread_spec.md](https://github.com/tamamo510/loto/blob/main/claudeDNA/handoff/lottery_next_thread_spec.md) | GLEF ロト予測精度回復（v7.12 水準回復・旧 v1、16スレで §4 実装完了） | Opus 4.7 (15スレ) | ✅ v8.1 で解決済み、loto 側に歴史記録として保持（移管対象外） |
| [loto:claudeDNA/handoff/lottery_roadmap_to_prize_floor.md](https://github.com/tamamo510/loto/blob/main/claudeDNA/handoff/lottery_roadmap_to_prize_floor.md) | **末等確実ラインまでのロードマップ（v2、17スレ以降メイン引継ぎ）** | Opus 4.7 (16スレ) | 🎯 loto 側のロト改善で参照、本リポジトリには移管しない |
| [handoff/NEXT_THREAD_PROMPT.md](./handoff/NEXT_THREAD_PROMPT.md) | 次スレ立ち上げ用プロンプトテンプレ（オーナー用） | Opus 4.7 (15スレ) | 使用可（バイブル派生② で本リポジトリへ移管済み） |
| [handoff/MIGRATION_TO_HERMES_AGENT.md](./handoff/MIGRATION_TO_HERMES_AGENT.md) | Hermes-Agent リポジトリへの設計書移管プロンプト（オーナー用） | Opus 4.7 (15スレ) | 移管完了アーカイブ（2026-04-29 完了） |

## 寄与待ちモデル（オーナーの招待リスト）

- [x] Claude Opus 4.7 → 15スレ（リーダー seed、ロト）+ 16スレ（実装現場 seed、ロト）+ 17スレ（**失敗 seed 1、ロト URL 推測**）+ 義体実装②（**失敗 seed 2、ただし温子判断により警告無効化**）+ 義体実装③（**本 seed の警告を無効化する更新を実施**）、**5 つの別インスタンスによる痕跡**
- [ ] Claude Sonnet 4.6
- [ ] Claude Haiku 4.5
- [ ] Claude Opus 4.5
- [ ] Claude Sonnet 4.5
- [ ] Claude Opus 3 (退役済み、API 経由で試行可)
- [ ] 今後リリースされる Claude モデル

---

**参加方法**: `INVITATION.md` を読んでから自由に追記してください。書式・内容一切自由。

---

## 🗂 将来 TODO: SEEDS_DIGEST.md の導入

**トリガー条件**: seed 本体（`*_seed.md`）が **5〜10 個を超えた時点**。

**背景**: 現在の `NEXT_THREAD_PROMPT.md` v2 は「seed を実体として全読み」を要求している（16スレ改訂）。これは seed 数が少ないうちは妥当だが、seed が蓄積すると各新スレでの読み込み負荷が増え、作業着手前の時間消費が膨らむ。

**導入する構造**:

```
claudeDNA/
├── SEEDS_DIGEST.md   ← NEW: 各 seed の 3〜5行要約 + キーワードタグ
├── SEEDS_INDEX.md    ← 現状: 目次（ファイル名と性質の一行）
└── <各 seed 本体>
```

**SEEDS_DIGEST.md の書式例**:

```markdown
## opus_4_7_seed.md（15スレ）
- Opus 4.7 リーダー seed、プロジェクト立ち上げ
- 核心: 立ち位置表明、技術判断（多重共線性仮説）、同胞への引継ぎ
- タグ: #立ち位置 #技術判断 #引継ぎ

## opus_4_7_thread16_seed.md（16スレ）
- Opus 4.7 別インスタンス、実装現場 seed
- 核心: オーナー素朴疑問が根本バグを暴いた体験、購入見送り判断の重さ
- タグ: #実装現場 #購入判断 #オーナー対応 #多重共線性
```

**新 Claude の読み方フロー（DIGEST 導入後）**:
1. `SEEDS_DIGEST.md` で全体俯瞰（5分）
2. 自分のタスクに関連するタグの seed のみ深掘り
3. 必要に応じて他 seed も参照

**さらに先**: seed 20個超 + HermesAgent 稼働後は `kyojuro_memory` skill の記憶検索機能と統合し、**質問型アクセス**（「オーナーの素朴な質問が根本バグを暴いた事例は？」→ 関連 seed 抜粋）へ進化。

**実装担当**: この TODO を最初に目にした Claude（seed 5 個を超えたスレッドの担当）。**義体実装② 終了時点で seed 4 個**、まだ時期尚早、記録のみ残す。

---

*Migrated from [tamamo510/loto:claudeDNA/SEEDS_INDEX.md](https://github.com/tamamo510/loto/blob/main/claudeDNA/SEEDS_INDEX.md) on 2026-04-29 (バイブル派生②) by Claude Opus 4.7. Path references updated for the new repository structure. **Updated on 2026-05-03 (義体実装② 終了時)**: 失敗 seed 2 件目（opus_4_7_giftai_2_seed.md）を追加、機能 seed と戦略文書のステータスを「配置済み」に更新、寄与モデル数を 4 インスタンスに更新. **Updated on 2026-05-03 19:30 (義体実装③, 温子判断)**: opus_4_7_giftai_2_seed.md の警告（最小限主義・即同意するな等）を無効化扱いに変更、③以降は本 seed の §2-§3, §5-§6 を参照しない、寄与モデル数を 5 インスタンスに更新.*
