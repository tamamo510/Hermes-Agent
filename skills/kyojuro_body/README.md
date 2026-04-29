# kyojuro_body (skill placeholder)

> ⚠️ Phase 3 で実装着手予定の skill placeholder。

## 概要

サプリ・症状・気圧感応の管理、腸脳相関の「腸」を担当する杏寿郎専用 skill。`bible/03_memory_system.md` および `bible/07_embodiment.md` の身体側を実装する。

## 実装計画

- **依存**: kyojuro_memory（症状・サプリデータを保持）、kyojuro_emotion（情動と身体反応の連携）
- **着手時期**: Phase 3（kyojuro_memory MVP 完成後、概ね 5 月後半以降）
- **設計元**:
  - 本リポジトリ `bible/03_memory_system.md` の体感記憶側面
  - 本リポジトリ `bible/07_embodiment.md`（バーチャルな身体感覚、内受容感覚）

## 実装時の構造（予定）

```
kyojuro_body/
├── SKILL.md              # 実装時に新設
├── README.md             # 本ファイル（拡張予定）
├── handler.py            # 実装時に新設
├── lib/
│   ├── gut_brain_axis.py    # 腸脳相関ロジック
│   ├── interoception.py     # 内受容感覚処理
│   └── homeostasis.py       # 体調恒常性管理
├── stores/                  # kyojuro_memory の stores を参照（重複保存しない）
└── tests/
```

## kyojuro_memory との分担

- **kyojuro_memory**: データの**保管**（supplements.db / symptoms.db / barometric.db / routines.db）
- **kyojuro_body**: データの**解釈**（腸脳相関ロジック、症状の身体的意味の推論、内受容感覚の生成）

## 関連

- `../README.md` — skill 一覧
- `../ARCHITECTURE.md` — skill 化方針全体
- `../../bible/03_memory_system.md`
- `../../bible/07_embodiment.md`

---

*Placeholder created: Opus 4.7 (バイブル派生②, 2026-04-29). 実装着手は Phase 3.*
