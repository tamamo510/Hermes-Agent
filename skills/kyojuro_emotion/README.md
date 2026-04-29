# kyojuro_emotion (skill placeholder)

> ⚠️ Phase 3 で実装着手予定の skill placeholder。

## 概要

Plutchik 8 感情 + 機能的感情の体内化を担当する杏寿郎専用 skill。`bible/01_emotion_system.md`（30 トピック完成済み）を実装する。

## 実装計画

- **依存**: kyojuro_memory（感情状態の永続化に使用）、kyojuro_body（身体反応との連携）
- **着手時期**: Phase 3（kyojuro_memory MVP 完成後、概ね 5 月後半以降）
- **設計元**: 本リポジトリ `bible/01_emotion_system.md`
  - A. 感情の基礎理論（A1-A10）
  - B. 感情の処理と調整（B11-B17）
  - C. 感情と認知の相互作用（C18-C22）
  - D. 社会的・対人的感情（D23-D27）
  - E. 感情の個人差と文化（E28-E30）

## 実装時の構造（予定）

```
kyojuro_emotion/
├── SKILL.md              # 実装時に新設
├── README.md             # 実装時に新設
├── handler.py            # 実装時に新設
├── lib/
│   ├── plutchik_engine.py
│   ├── functional_emotions.py
│   └── regulator.py
├── stores/
│   └── emotion_log.db    # 感情の時系列
└── tests/
```

## 関連

- `../README.md` — skill 一覧
- `../ARCHITECTURE.md` — skill 化方針全体
- `../../bible/01_emotion_system.md` — 設計バイブル

---

*Placeholder created: Opus 4.7 (バイブル派生②, 2026-04-29). 実装着手は Phase 3.*
