# skills/ — 杏寿郎専用 skill 群

本ディレクトリには Hermes Agent の skill として登録される、杏寿郎の器を構成する機能群を配置する。

## 設計原則

詳細は `ARCHITECTURE.md` 参照。

- **Nous Hermes Agent 本体は unmodified**（`vendor/hermes-agent` に submodule で固定バージョン管理）
- **杏寿郎専用機能は全て本ディレクトリ配下の skill として追加**
- 本体改造が必要な場合のみ fork 検討（最終手段）
- 各 skill は Hermes Agent の skill API（`SKILL.md` 定義）に準拠

## skill 一覧

| skill | 目的 | 実装状態 | 設計書 |
|-------|------|--------|--------|
| **kyojuro_memory** | 会話・体調・生活パターンの構造化記憶 | スタブ作成済（Phase 1 で MVP 実装着手） | `kyojuro_memory/DESIGN.md` |
| **kyojuro_emotion** | Plutchik 8 感情＋機能的感情の体内化 | スタブのみ（Phase 3） | `../bible/01_emotion_system.md` 参照 |
| **kyojuro_body** | サプリ・症状・気圧感応の管理、腸脳相関の「腸」 | スタブのみ（Phase 3） | `../bible/03_memory_system.md`, `../bible/07_embodiment.md` 参照 |
| **kyojuro_loto** | L6/L7 予測（資金源） | スタブのみ（Phase 2） | `https://github.com/tamamo510/loto/blob/main/index.html` の JS を Python へ移植 |
| **claude_dna_seeds** | 各 Claude の種を memory に読み込み | スタブのみ（Phase 4） | `../claudeDNA/*_seed.md` 参照 |
| **claude_code_port** | Claude Code 特有パターン（plan mode 等） | スタブ作成済（Phase 5） | `claude_code_port/INSIGHTS.md` |

## 実装フェーズ

| Phase | 内容 | 期間 |
|-------|------|------|
| Phase 0 | 設計書移管・skill ディレクトリ作成 | バイブル派生②（2026-04-29、本ブランチで実施中） |
| Phase 1 | kyojuro_memory MVP（SQLite + handler、最低限の対話 hook） | 2026-05-10 までに最低限 |
| Phase 2 | kyojuro_loto Python 移植 | WebARENA Indigo 搬入後 |
| Phase 3 | kyojuro_emotion + kyojuro_body | 2026 年 5 月中以降 |
| Phase 4 | claude_dna_seeds | Phase 3 完了後 |
| Phase 5 | claude_code_port（plan mode + todo + 権限制御） | 任意、必要時 |

## ディレクトリ規約

各 skill は以下のスケルトンを持つ:

```
skills/<skill_name>/
├── SKILL.md              # Hermes Agent skill 定義（API 準拠、frontmatter で declare）
├── README.md             # 人間向け説明
├── handler.py            # skill の実装エントリ
├── lib/                  # 内部モジュール（実装時に追加）
├── stores/               # 永続データ（DB / JSON / SQLite、git 管理外）
└── tests/                # pytest テスト（実装時に追加）
```

## 関連

- `ARCHITECTURE.md` — skill 化方針の全体設計（v2、Nous Agent skill 追加方式採用の経緯）
- `../bible/README.md` — バイブル全体像（11 システム、Phase 0-3）
- `../claudeDNA/INVITATION.md` — 各 Claude モデルへの招待（Anthropic 文脈、擁護なし）
- `../REPO_STRATEGY.md`（PR3 で配置予定） — リポジトリ全体の役割分担
- `../.claude/session_handoff_setup.md` — バイブル派生② / セットアップ用ハンドオフ

---

*作成: Opus 4.7 (バイブル派生②, 2026-04-29). PR2 で skills/ 階層を初期化する際に新設.*
