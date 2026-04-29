# kyojuro_loto (skill placeholder)

> ⚠️ Phase 2 で実装着手予定の skill placeholder。資金源 skill のため優先度高。

## 概要

L6/L7 予測（杏寿郎・温子のマイホーム資金源）を担当する杏寿郎専用 skill。loto リポジトリの `index.html` 内 JavaScript ロジックを Python へ移植する。

## 実装計画

- **依存**: なし（独立 skill）
- **着手時期**: Phase 2（kyojuro_memory MVP 完成後、WebARENA Indigo 搬入後）
- **実装元**: https://github.com/tamamo510/loto/blob/main/index.html
  - GLEF v8.1.1 の予測ロジック（14 Wave + Bayesian + Bootstrap + HMM + KDE 内部統合 + Lyapunov 乗算調整 + Wavelet）
  - CMA-ES（14 次元、sigma0=0.5、maxGen=100）
  - 適応的 Exclusion（Weibull + HMM fusion）
  - Bootstrap Confidence（B=200）

## 実装時の構造（予定）

```
kyojuro_loto/
├── SKILL.md              # 実装時に新設
├── README.md             # 本ファイル（拡張予定）
├── handler.py            # 実装時に新設（Hermes Agent から呼べるエントリ）
├── lib/
│   ├── waves/                # 14 Wave の各実装
│   │   ├── depth_wave.py
│   │   ├── vert_wave.py
│   │   ├── ... (全 14 種)
│   ├── bayesian.py
│   ├── bootstrap.py
│   ├── cma_es.py
│   ├── hmm.py
│   └── exclusion.py
├── data/
│   ├── loto6.csv          # 抽選データ（loto リポジトリと同期）
│   └── loto7.csv
├── stores/
│   ├── learnedParams_l6.json   # CMA-ES 学習結果
│   ├── learnedParams_l7.json
│   └── predictions.jsonl       # 予測蓄積
└── tests/
    └── test_parity.py     # JS 版との数値一致テスト
```

## 移植時の注意

- **数値再現性が最重要**: 初期段階では JS 版の Tuned 予測を **完全再現** することを目標とする
- **データリーク禁止**: N 回目の予測には N-1 回までのデータのみ使用（loto 側 CLAUDE.md 絶対ルール）
- **誇張禁止**: BT 数値は正直に報告、ランダム基準（L6: 0.84, L7: 1.32）との差を必ず明記
- **末等止まりは失敗**: 高額当選（2 等以上相当）に届く精度のみ意味がある

## Phase 2 のマイルストーン

| マイルストーン | 期待値 |
|----------|------|
| JS → Python 数値一致確認 | L7 Tuned ±0.05 以内で再現 |
| 末等確実ライン到達 | L7 Tuned ≥ 4.0, Max ≥ 5, Prize ≥ 15/20 |
| 1 等射程到達 | L7 Tuned ≥ 6.5（マイホーム資金ビジョン）|

## 関連

- `../README.md` — skill 一覧
- `../ARCHITECTURE.md` — skill 化方針全体（§4 Phase 2）
- 移植元 https://github.com/tamamo510/loto/blob/main/index.html
- 進捗ロードマップ https://github.com/tamamo510/loto/blob/main/claudeDNA/handoff/lottery_roadmap_to_prize_floor.md

---

*Placeholder created: Opus 4.7 (バイブル派生②, 2026-04-29). 実装着手は Phase 2.*
