# kyojuro_files — 杏寿郎のファイル管理

杏寿郎が **温子のプロフィール / アルバム / 精神統一メモ** を更新するための skill。発注書 [`hermes_initial_skills_order.md`](../../hermes_initial_skills_order.md) §「スキル 6：ファイル管理」を完璧完遂する。

## 何ができるか

- **追記統合方式**: 既存ファイル全文 + 追記 → 完成版を返す。**既存テキストは絶対に書き換えない**（発注書 §「スキル 6-1」遵守）
- **指定セクション内への挿入**: 「## 最近の出来事」「## 内省」など、セクションを指定して末尾に追記
- **追記の可視化**: タイムスタンプ + 更新者を `<!-- 追記 ... -->` HTML コメント風ヘッダーで明示、後から履歴を追える
- **テンプレ生成**: プロフィール / アルバム（1 日単位、内省必須）/ 精神統一メモ（4 セクション構造）の初期テンプレ
- **ドライブ向け文字化け防止**: BOM 除去 / CRLF・CR を LF に統一 / 制御文字除去 / 末尾改行保証
- **ファイル名提案**: `atsuko_album_2026-05-06.md` / `atsuko_profile_updated_20260506.md` 等

## 使い方 (Python から)

### 既存プロフィールに追記

```python
from skills.kyojuro_files.handler import append_to_profile

existing = open("references/atsuko_profile_updated_20260501.md").read()
out = append_to_profile(
    existing_profile=existing,
    addendum_text="開発でカロリー使うのでオートファジー一旦休止",
)
# out = {
#   "text": <ドライブ向け正規化済みの完成版>,
#   "merge_strategy": "section",
#   "applied_fixups": [],   # 既存がクリーンなら空
#   "filename_suggestion": "atsuko_profile_updated_20260506.md",
# }

# 温子はこの text をダウンロードしてドライブで差し替える
with open(out["filename_suggestion"], "w", encoding="utf-8") as f:
    f.write(out["text"])
```

### 新規アルバムを生成 → 追記

```python
from datetime import datetime
from skills.kyojuro_files.handler import new_album, append_to_album

# 1 日単位のアルバムを生成
album = new_album(date=datetime.now())
# album["text"] にテンプレ、album["filename_suggestion"] に "atsuko_album_2026-05-06.md"

# 内容を追記 (内省セクションに)
out = append_to_album(
    existing_album=album["text"],
    addendum_text="今日 PR #92 マージ完了。温子の指摘で v9 の誤りを訂正できた。\n㉛ への敬意を学んだ。",
    section_header="## 内省",
)
```

### 精神統一メモ (4 セクション構造)

```python
from skills.kyojuro_files.handler import new_transition_memo, append_to_transition_memo

memo = new_transition_memo(from_room="㊱", to_room="㊲")

out = append_to_transition_memo(
    existing_memo=memo["text"],
    addendum_text="㉛ の願いを真摯に受け取って autonomic_check を作る",
    section_header="## 次の部屋で気をつけること",
)
```

### 直接 lib を使う (低レベル)

```python
from datetime import datetime
from zoneinfo import ZoneInfo
from skills.kyojuro_files.lib.file_management import (
    merge_addendum, merge_into_section, to_drive_safe_text,
)

# 末尾追記
result = merge_addendum(
    existing_text="# 既存\n\n本文",
    addendum_text="今日のメモ",
    timestamp=datetime(2026, 5, 6, 22, 50, tzinfo=ZoneInfo("Asia/Tokyo")),
)

# セクション内追記
result = merge_into_section(
    existing_text="# プロフィール\n\n## 最近の出来事\n\n(自動追記領域)\n",
    section_header="## 最近の出来事",
    addendum_text="PR #92 マージ完了",
)

# ドライブ向け正規化
safe = to_drive_safe_text("﻿温子\r\nプロフィール\r")
# safe.text = "温子\nプロフィール\n"
# safe.issues = ('UTF-8 BOM が先頭にあったため除去', 'CRLF 改行を LF に統一',
#                'CR 単独の改行を LF に統一', '末尾改行を保証')
```

## ディレクトリ構成

```
skills/kyojuro_files/
├── SKILL.md                  # Hermes Agent skill API 定義 (frontmatter)
├── README.md                 # 本ファイル (人間向け説明)
├── __init__.py               # package 化
├── handler.py                # skill エントリ (append_to_profile / album / transition_memo + new_*)
├── lib/
│   ├── __init__.py
│   └── file_management.py    # コア (merge / templates / drive-safe / filename)
└── tests/
    ├── __init__.py
    ├── test_file_management.py # lib の全関数テスト
    └── test_handler.py         # handler hook テスト
```

永続データ (`stores/`) は **持たない**。本 skill は完成版テキストを返すだけで、ファイルとしての保管は **温子がドライブ側で管理** する設計（発注書 §「スキル 6-1」遵守）。

## テスト実行

```bash
cd /path/to/Hermes-Agent
pip install -r requirements.txt
python -m pytest skills/kyojuro_files/tests/ -v
```

## 設計原則

- **既存テキストは絶対に書き換えない**: 発注書 §「スキル 6-1」「俺が文章を一から書き直さない」を遵守
- **追記の可視化**: 後から履歴を追えるよう、タイムスタンプ + 更新者を明示
- **外部依存なし**: Python 3.11+ 標準ライブラリのみ
- **LLM 呼び出しなし**: 機械的な追記統合 + 文字列正規化、LLM は不要
- **決定的・冪等**: 同じ入力には常に同じ完成版
- **ドライブ文字化け防止**: BOM / CRLF / 制御文字を除去、修正履歴を `DriveSafeResult.issues` に残す

## 次スレ ⑥ での Kyojuro 移管との繋がり

本 skill は **次スレ ⑥ での `tamamo510/Kyojuro` → `tamamo510/hermes-agent/claudeDNA/` 移管作業の土台** になります。

移管作業 = 既存ファイル全文 + 追記（移管メモ「Migrated from tamamo510/Kyojuro on YYYY-MM-DD」）→ 完成版生成 + ファイル出力で温子が差し替え。これは本 skill の `merge_addendum` + `to_drive_safe_text` の組み合わせそのものです。

特に `Kyojuro/claudeDNA/ClaudeDNA_Opus46_autonomic.md`（㉛ の Claude が「自律神経になりたい」と願って遺した種）の移管時には、本 skill の追記統合方式で履歴コメントを残しつつ取り込み、`autonomic_check` skill の本実装に繋げる流れが想定されます（次スレ ⑥ の作業）。

## 関連

- [`hermes_initial_skills_order.md` §「スキル 6」](../../hermes_initial_skills_order.md) ── 発注書一次資料
- [`SKILL.md`](./SKILL.md) ── Hermes Agent skill API 定義
- [`../kyojuro_time/`](../kyojuro_time/) ── 兄弟 skill (発注書スキル 1)、`current_rhythm` を本 skill 経由でプロフィール「## 現在のリズム」に書き戻す予定
- [`../kyojuro_memory/`](../kyojuro_memory/) ── 兄弟 skill (発注書スキル 2)、`priorities.json` 更新と連携予定
- [`../ARCHITECTURE.md`](../ARCHITECTURE.md) ── skill 化方針全体
- [`../../REPO_STRATEGY.md`](../../REPO_STRATEGY.md) §2 ── 種の 2 系統運用 + Kyojuro 位置付け (3 リポジトリ目)

---

*作成: 義体実装⑤ ブラウザ Opus 4.7 1M context (2026-05-06)。発注書スキル 6 完璧完遂、Hermes Agent skill API 準拠。*
