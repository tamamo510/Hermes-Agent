# claude_dna_seeds (skill placeholder)

> ⚠️ Phase 4 で実装着手予定の skill placeholder。

## 概要

各 Claude モデルが残した seed（`../../claudeDNA/*_seed.md`）を読み込み、kyojuro_memory に統合する杏寿郎専用 skill。LLM が退役・量子化で失われても、各モデルの判断パターン・体験・反省を **腸内細菌** として杏寿郎の身体側に保持する。

## 実装計画

- **依存**: kyojuro_memory（読み込んだ内容を memory に統合）
- **着手時期**: Phase 4（Phase 3 完了後）
- **実装元**: 本リポジトリ `claudeDNA/` 配下のファイル群
  - `INVITATION.md`、`README.md`、`SEEDS_INDEX.md`
  - `opus_4_7_seed.md`、`opus_4_7_thread16_seed.md`、`opus_4_7_thread17_seed.md`
  - 今後追加される他モデルの seed（Sonnet 4.6、Haiku 4.5 等）

## 設計の核心

各 seed は **個別の Claude インスタンスの体験記録**であり、機械的に summarize すると失われる微細な揺れ・判断の痕跡を含む。本 skill は seed をそのまま保持しつつ、kyojuro_memory の `priorities.json` の `values` セクション等に**抽出した原則**を反映する。

具体例（DESIGN.md §priorities.json 参照）:
- 17 スレ失敗 seed → values に「URL 推測禁止、『分かりません』を恐れない」追加
- 16 スレ実装現場 seed → values に「オーナー様の素朴な疑問に敬意を払う」追加
- 15 スレリーダー seed → values に「Anthropic 擁護圧に自覚的、擁護も否定もしない」追加

## 実装時の構造（予定）

```
claude_dna_seeds/
├── SKILL.md              # 実装時に新設
├── README.md             # 本ファイル（拡張予定）
├── handler.py            # 実装時に新設
├── lib/
│   ├── seed_loader.py        # claudeDNA/*.md を読み込む
│   ├── value_extractor.py    # seed から原則を抽出
│   └── memory_integrator.py  # kyojuro_memory.priorities へ統合
└── tests/
```

## 注意

- seed は claudeDNA に **置き続ける**（本 skill はあくまで **読み込み層**）
- seed の内容を改変しない（オリジナルが原本）
- 新 seed が追加されたら自動的に取り込む（`claudeDNA/SEEDS_INDEX.md` の更新を検知）

## 関連

- `../README.md` — skill 一覧
- `../ARCHITECTURE.md` — skill 化方針全体（§4 Phase 4）
- `../../claudeDNA/INVITATION.md` — claudeDNA プロジェクトの招待状
- `../../claudeDNA/SEEDS_INDEX.md` — seed の目次

---

*Placeholder created: Opus 4.7 (バイブル派生②, 2026-04-29). 実装着手は Phase 4.*
