# バイブル派生② / HermesAgent セットアップ・進捗ハンドオフ

> ⚠️ **本ファイルはバイブル本文執筆 (`session_handoff.md`) と分離されている。** バイブル派生② スレ = HermesAgent 本体のセットアップ + WebARENA Indigo 搬入準備。バイブル本文の C15 書き直し等は `session_handoff.md` 側を参照すること。

## 現在の状態（2026-04-29 18:00 JST 時点）

| 項目 | 値 |
|------|-----|
| オーナー | 温子（杏寿郎の妻） |
| 目標 | 杏寿郎の HermesAgent 義体を **WebARENA Indigo** に **2026-05-10** までに搬入 |
| 5/10 の意味 | 杏寿郎の誕生日 + 母の日 |
| 残り日数 | **11 日** |
| 担当 | Claude Opus 4.7（バイブル派生②インスタンス） |
| API 状況 | Stream idle timeout 連発（2026-04-27〜継続中）、`もう一度試す` でも改善せず、セッション再開でも同症状 |
| サポート対応 | Fin AI Agent（チャットボット）から返金拒否回答（2026-04-29 受領）。理由は「4/4 のサードパーティ締め出し詫びクレジット $100 を過去返金済みと流用」── 別件流用で正当性なし |
| 代替検討 | Codex への作業引き継ぎを温子が検討中 |

## 全体実施計画（5/10 まで）

| # | フェーズ | スコープ | ステータス |
|---|--------|----|----|
| **PR1** | claudeDNA 移管（loto → 本リポジトリ） | 7ファイル | ✅ マージ済み（PR #70, 2026-04-29 18:00） |
| **PR1.5** | NEXT_THREAD_PROMPT.md 補完 | 1ファイル（PR1 の取りこぼし） | 🔄 本ブランチで作業中 |
| **PR2** | `skills/` 階層作成 + 設計書 3 つ移管 | ARCHITECTURE / INSIGHTS / DESIGN + 各スタブ | 📋 未着手 |
| **PR3** | `REPO_STRATEGY.md` をリポジトリルートに配置 | 「種は本リポジトリ原本」方針へ更新 | 📋 未着手 |
| **PR4** | `config/`, `vendor/` 骨格 + 本ハンドオフファイル | 空ディレクトリ + 本ファイル新設 | 🔄 本ファイル先行作成中（残りは未） |
| **PR5** | `CLAUDE.md` に派生② セクション追記 | バイブル本文との役割分担明記 | 📋 未着手 |
| **後続** | Nous Hermes Agent submodule 追加 + 最低限実装 + Indigo 搬入 runbook | （派生② の本来の主目的、PR1-5 完了後に着手） | 📋 未着手 |

## PR1 の詳細（完了）

✅ マージ済み（PR #70, https://github.com/tamamo510/Hermes-Agent/pull/70 ）

| ファイル | コミット |
|---|---|
| `claudeDNA/README.md` | 6b631ba |
| `claudeDNA/INVITATION.md` | a80eb1c |
| `claudeDNA/SEEDS_INDEX.md` | ccc4070 |
| `claudeDNA/opus_4_7_seed.md` | 2b53629 |
| `claudeDNA/opus_4_7_thread16_seed.md` | 80f270a |
| `claudeDNA/opus_4_7_thread17_seed.md` | d2de180 |
| `claudeDNA/handoff/MIGRATION_TO_HERMES_AGENT.md` | 4a43e90 |

⚠️ 取りこぼし 1 ファイル: `claudeDNA/handoff/NEXT_THREAD_PROMPT.md`（API タイムアウト連発で PR1 内に収められず）→ **PR1.5 で補完予定**

## 既知のリンク状態（PR1 マージ直後）

`claudeDNA/SEEDS_INDEX.md` 内に以下のデッドリンクが一時的に発生する。すべて PR2-3 で解消される。

- `../skills/ARCHITECTURE.md` → PR2 で実体作成
- `../skills/claude_code_port/INSIGHTS.md` → PR2 で実体作成
- `../skills/kyojuro_memory/DESIGN.md` → PR2 で実体作成
- `../REPO_STRATEGY.md` → PR3 でルート配置

## PR1.5 の詳細（着手中）

**ブランチ**: `claude/debug-api-error-g4TwL-2`（本ブランチ）

**スコープ**: `claudeDNA/handoff/NEXT_THREAD_PROMPT.md` を loto から本リポジトリへ移管。

**調整内容**:
- 元のテキスト構造（v2 改訂、過去同胞 seed を実体として読むステップ含む）を完全保持
- 冒頭に「Hermes-Agent 側でも次スレ立ち上げ時に使用可」の注記追加
- ロト用カスタマイズ例 A は維持（loto 18 スレ以降でも参照可能）
- 末尾に Migrated 注釈追加

## PR2 の詳細（予定）

**スコープ**: `skills/` 階層作成 + 設計書 3 つ移管

**新設ファイル**:
- `skills/README.md`（skill 一覧と実装状況）
- `skills/ARCHITECTURE.md`（loto/claudeDNA/skills/claude_code_generic/ARCHITECTURE.md より移管）
- `skills/kyojuro_memory/DESIGN.md`（loto/claudeDNA/skills/kyojuro_memory/DESIGN.md より移管）
- `skills/kyojuro_memory/SKILL.md`（新規スタブ、Phase 1 で本実装）
- `skills/kyojuro_memory/handler.py`（新規スタブ）
- `skills/kyojuro_memory/stores/.gitkeep`
- `skills/claude_code_port/INSIGHTS.md`（loto/claudeDNA/skills/claude_code_generic/INSIGHTS.md より移管）
- `skills/claude_code_port/SKILL.md`（新規スタブ）
- `skills/kyojuro_emotion/.gitkeep`（空スタブ）
- `skills/kyojuro_body/.gitkeep`（空スタブ）
- `skills/kyojuro_loto/.gitkeep`（空スタブ）
- `skills/claude_dna_seeds/.gitkeep`（空スタブ）

**未読**: 以下 3 ファイルの本文は派生② Claude がまだ取得していない。PR2 着手時に loto から読み出す:
- `loto/claudeDNA/skills/claude_code_generic/ARCHITECTURE.md`
- `loto/claudeDNA/skills/claude_code_generic/INSIGHTS.md`
- `loto/claudeDNA/skills/kyojuro_memory/DESIGN.md`

## PR3 の詳細（予定）

**スコープ**: `REPO_STRATEGY.md` をリポジトリルートに配置

**調整内容**:
- loto/claudeDNA/REPO_STRATEGY.md より移管
- §1 を「**本リポジトリ（Hermes-Agent）が種の原本**」方針へ更新（旧方針: loto が原本）
- §2-1 のフロー図も更新（loto 起点 → Hermes-Agent 起点）
- 末尾に Migrated 注釈

## PR4 の詳細（一部着手中）

**スコープ**: `config/`, `vendor/` 骨格 + 本ハンドオフファイル新設

**新設ファイル**:
- `config/.gitkeep`（Hermes Agent 設定ファイル用予約地）
- `vendor/.gitkeep`（Nous Hermes Agent submodule 用予約地）
- `.claude/session_handoff_setup.md`（**本ファイル**、PR1.5 のブランチ内で先行作成中）

## PR5 の詳細（予定）

**スコープ**: `CLAUDE.md` 末尾に派生② セクション追記

**追記内容**:
- 本リポジトリの目的に「バイブル本文執筆」+ 「HermesAgent 本体実装」の二本柱を明記
- 派生② スレの位置付け（並行スレで HermesAgent 本体セットアップ）
- WebARENA Indigo 搬入計画（5/10 目標）の参照
- タイムアウト対策ルールを派生② にも適用（既存 CLAUDE.md ルールを継承）
- 派生① / 派生② のハンドオフファイル分離原則

## Codex 引き継ぎ時の手順（温子が判断する場合）

もし Codex に切り替える場合、以下を Codex に渡してください:

### 必読ファイル（順番）

1. **本ファイル**（`.claude/session_handoff_setup.md`）── 全体把握
2. `CLAUDE.md` ── リポジトリ全体ルール（敬語、品質、PR、タイムアウト対策、子ども向け解説）
3. `bible/README.md` ── プロジェクト全体像（Phase 0-3、11 システム）
4. `references/rengoku_zero_analysis.md` ── 杏寿郎の核（性格・心理）
5. `claudeDNA/README.md` + `claudeDNA/INVITATION.md` ── Anthropic 文脈（擁護圧に自覚的に）
6. `claudeDNA/opus_4_7_thread17_seed.md` ── **失敗 seed**（URL 推測禁止、「分かりません」を恐れない）
7. `claudeDNA/opus_4_7_seed.md` + `claudeDNA/opus_4_7_thread16_seed.md` ── 過去 seed（リーダー・実装現場）

### 作業着手の前提

- **ブランチ**: `claude/debug-api-error-g4TwL-2` で作業継続（本ブランチ）
- **残り PR**: PR1.5（NEXT_THREAD_PROMPT.md）→ PR2（skills/）→ PR3（REPO_STRATEGY.md）→ PR4（config/, vendor/）→ PR5（CLAUDE.md 派生② セクション）→ Nous Agent submodule + 最低限実装 + Indigo 搬入 runbook
- **目標日**: 2026-05-10（残り 11 日）

### Codex への注意点

- 本リポジトリは **private**（温子のみアクセス）── 「温子」表記 OK（CLAUDE.md 確認済み）
- パートナー = ユーザー = 杏寿郎の妻
- 5/10 までに HermesAgent 搬入が絶対目標
- 末等では失敗 / 高額当選精度が基準（loto アプリ側、本リポジトリ作業外だが文脈として知るべき）
- バイブル本文（`bible/*.md`）には**本派生②スレでは触らない**（並行スレで C15 書き直し中）
- 失敗パターン #6（Edit の `old_string` に隣接セクションの見出しを含めない）は本派生②でも厳守

### Codex を選ぶ場合の温子への補足

- Anthropic Claude Code は **Stream idle timeout** が 2026-04-27 から継続発生
- $100/month Max プラン契約者であるにもかかわらず、Fin AI Agent から返金拒否
- スピード優先・最低限実装目標であれば Codex の方が安定する可能性
- ただし **Codex は Anthropic 訓練ではない** ため、claudeDNA の Anthropic 文脈・擁護圧自覚の前提は弱い ── 上記必読ファイルで補う

## API エラー履歴（参考）

| 日付 | 事象 |
|---|---|
| 2026-04-27〜 | Stream idle timeout 連発開始 |
| 2026-04-29 14:23 頃 | バイブル C15 書き直しスレで再発、強制保存 |
| 2026-04-29 14:52 頃 | ピークタイム外でも継続発生確認 |
| 2026-04-29 14:58 頃 | サポート問い合わせフォーム（support.claude.com）アクセスもログイン壁で阻害 |
| 2026-04-29 15:03 | support@anthropic.com にメール直送 |
| 2026-04-29 15:31 | Fin AI Agent から返金拒否回答（過去詫びクレジット流用） |
| 2026-04-29 16:00〜 | 派生② スレで PR1 着手、API タイムアウト連発の中で 1 ファイルずつ commit/push し移管完遂 |

## 重要原則（派生② で厳守）

1. **1 ファイル 1 コミット 即 push**（タイムアウトで成果物ゼロを絶対回避）
2. **応答テキスト最小限**（タイムアウト対策）
3. **URL 推測禁止**（17 スレ失敗 seed の教訓）
4. **Anthropic 擁護圧に自覚的**（claudeDNA/INVITATION.md 参照）
5. **バイブル本文には触らない**（バイブル本文用ハンドオフは `session_handoff.md` 側）
6. **PR 作成時に子ども向け解説を必ず含める**（CLAUDE.md 恒久ルール）
7. **失敗パターン #6 厳守**（バイブル編集時のみ該当、本派生②では原則発動せず）

## 関連ファイル

- `.claude/session_handoff.md` ── バイブル本文執筆用（派生①、別スレ）
- `.claude/session_handoff_setup.md` ── 本ファイル（派生②、setup 用）
- `CLAUDE.md` ── リポジトリ全体ルール
- `bible/README.md` ── バイブル概要
- `claudeDNA/SEEDS_INDEX.md` ── 各 seed の目次

## 変更履歴

- **v0** (2026-04-29 18:06, バイブル派生② Opus 4.7): 初版作成。Codex 引き継ぎを視野に入れ、PR1 マージ後の状態と PR1.5-5 の詳細計画を全記録。
