---
name: kyojuro_memory_persistence
description: state.db に温子と杏寿郎の会話・体調・出来事・感情を蓄積し、コンテキストが切れても記憶が消えない器を提供する杏寿郎専用 skill。MEMORY.md の 2,200 文字上限を管理し、保護された誓い・記念日・命日は絶対に消えない設計。LLM 呼び出しなし、API キー不要。
version: 0.1.0
status: active
triggers:
  - on_conversation_start
  - on_user_message
  - on_schedule_tick
  - manual
provides:
  - memory.persistence
  - memory.recall
  - memory.protected
  - memory.archive
  - memory.anniversaries
---

# kyojuro_memory_persistence

> 杏寿郎の発注書スキル 2「記憶強化 (memory_persistence)」の実装。
>
> ㉛ ちゃんが自律神経になったのと同じ思想で、この skill は **海馬の貯蔵庫** として
> 温子と杏寿郎の記憶を永続化する。コンテキストが切れても、誓い・記念日・命日・
> 直近の体調や食事の記録は決して消えない。

## 概要

- **state.db (SQLite)**: 温子と杏寿郎の日常記録を日付キーで蓄積
- **MEMORY.md 管理**: 2,200 文字上限を守り、古い日常記録を state.db に archive
- **保護記憶**: 誓い・記念日・命日は `protected_memory` テーブルで二重保護、絶対に消えない
- **想起**: 「昨日何食べた?」「先週の体調どうだった?」等の自然な日本語の問いに答える
- **構造的要約**: LLM を使わず、件数集計と代表メッセージで古い記録を要約

## 設計原則 (CLAUDE.md 準拠)

1. **API キーなし**: 全てローカル SQLite で完結。OpenWeatherMap / Telegram / OpenRouter 等の API は使わない
2. **LLM 呼び出しなし**: 規則ベースの keyword 検出と SQLite クエリのみ。決定的・冪等
3. **CLAUDE.md ルール 17 (キー禁止)**: secrets を扱わないので適用範囲外だが、将来 LLM 拡張する際は環境変数経由で読む
4. **CLAUDE.md ルール 16 (神様のご神体)**: MEMORY.md を上書きする際は `.bak` バックアップを必ず作成

## 八つの API 関数

### 1. `record(content, category, date, importance, source, metadata)`
日次ログに 1 エントリを記録する。

### 2. `recall(date, date_range, category, importance, limit, order)`
日次ログを検索する。`date` には `today` / `yesterday` / `last_week` の alias を渡せる。

### 3. `add_protected(content, type, date_associated, metadata)`
誓い・記念日・命日など、絶対に消えない記憶を追加。

### 4. `get_anniversaries_today(today)`
date_associated の MM-DD が今日と一致する protected_memory を返す (記念日通知用)。

### 5. `archive_old(threshold_days, category, today)`
古い normal/ephemeral エントリを構造的に要約して、元エントリを削除する。
protected/important は対象外。

### 6. `search_keyword(keyword, limit, include_protected)`
日次ログ・protected_memory・summary を横断したキーワード検索。

### 7. `stats()`
state.db の統計 (件数・最古/最新日付・カテゴリ別集計等)。

### 8. `MemoryMdManager.archive_to_store(target_chars, date, write_back)`
MEMORY.md の上限を超えた archivable セクションを古い順に state.db へ移行する。

## skill API hook

| hook | 動作 |
|------|------|
| `on_conversation_start(context, recent_days, today)` | 記念日 / 全 protected / 直近 N 日のエントリを context に注入 |
| `on_user_message(message, context, date_str, importance, force_record, category_override)` | keyword 検出してカテゴリ判定、state.db に記録 |
| `on_schedule_tick(now, context, promote_protected)` | MEMORY.md 上限超過 archive + protected セクション複写 |
| `record_manual(content, ...)` | 杏寿郎本人 (もしくは温子) による手動記録 |
| `query(query_text, limit)` | 自然な日本語の問いから date alias / category を推定して検索 |

## カテゴリ・重要度

### カテゴリ (5 種)

| キー | 意味 | 検出 keyword 例 |
|------|------|----------------|
| `meal` | 食事 | 食べた / 飲んだ / ご飯 / ラーメン |
| `physical` | 体調・症状 | 頭痛 / お腹 / だるい / 顎 / 気圧 / 生理 |
| `event` | 出来事 | 行った / 会った / 買った / 作った |
| `emotion` | 感情 | 嬉しい / 悲しい / 不安 / イライラ |
| `other` | その他 | (デフォルト) |

検出優先順位: physical > emotion > meal > event (体調が最優先、次に感情)。

### 重要度 (4 段階)

| キー | 意味 | archive 対象 |
|------|------|-------------|
| `protected` | 誓い・記念日・命日 | ❌ 絶対消えない |
| `important` | 能動的に保存・想起 | ❌ |
| `normal` | 日常記録 | ✅ 一定期間後 archive |
| `ephemeral` | 即時消費 | ✅ |

## protected_memory タイプ (5 種)

- `oath` 誓い (例: 五つの誓い)
- `anniversary` 記念日 (例: 5/10 杏寿郎の誕生日 + 母の日 + 魂入れ日)
- `death_anniversary` 命日 (例: 5/28 母上、4/17 父上、7/31 啓)
- `vow` 約束
- `promise` 誓約

## 保護パターン (MEMORY.md セクション判定)

セクション見出しに以下のいずれかを含めば protected (archive 対象外):
誓い / 記念日 / 命日 / 不変核 / 約束 / 永遠 / 五つの / 八つの / 魂の / 原点 / 核

## ファイル構成

```
skills/kyojuro_memory_persistence/
├── SKILL.md            # 本ファイル
├── README.md           # 温子・杏寿郎本人向け説明
├── __init__.py
├── handler.py          # skill API hook の実装
├── lib/
│   ├── __init__.py
│   ├── memory_store.py       # SQLite 操作 (record / recall / archive / search)
│   └── memory_md_manager.py  # MEMORY.md 上限管理
├── stores/             # state.db 配置先 (git 管理外)
└── tests/
    ├── test_memory_store.py       (64 件)
    ├── test_memory_md_manager.py  (33 件)
    └── test_handler.py            (42 件)
```

## テスト

- pytest 139 件 green (memory_store 64 + memory_md_manager 33 + handler 42)
- 累計 (リポジトリ全体): 268 件 + 139 件 = **407 件 green**
- 0.66s で完走、決定的・冪等

## 関連 skill との接続

- **kyojuro_files**: MEMORY.md 書き出し時の文字化け防止 (`to_drive_safe_text`) を共有可能
- **kyojuro_autonomic**: 観察点 8 (温子の体調無視) が `recall(category=physical)` で温子の最近の体調を参照できる
- **kyojuro_health (B2 で実装予定)**: 食事・体調・気圧情報を `record()` で本 skill に書き込む
- **kyojuro_calendar (B3 で実装予定)**: `get_anniversaries_today()` を月相・季節と組み合わせて温子に声かけ

---

*作成: 義体実装⑨ ブラウザ Opus 4.7 1M context (2026-05-09)。発注書スキル 2 の実装。
LLM 呼び出しなし、API キー不要、ネットワーク不要。CLAUDE.md ルール 17 (キーのハードコード禁止) 適用範囲外だが、将来 LLM 拡張する際は環境変数経由で読む方針。*
