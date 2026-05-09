---
name: kyojuro_search
description: DuckDuckGo Instant Answer + Wikipedia (ja/en) を統合したネット検索スキル。API キー不要のパブリック API のみを使用。LLM 呼び出しなし。
version: 0.1.0
status: active
triggers:
  - on_user_message
  - manual
provides:
  - search.combined
  - search.wikipedia_only
  - search.duckduckgo_only
---

# kyojuro_search

> 杏寿郎の発注書スキル 6「ファイル管理 + ネット検索」追補としての web_search 機能。
>
> ファイル管理 (`kyojuro_files`) は既に実装済み。本 skill は **ネット検索の臓器** を提供する。
> Indigo のインターネット接続を使い、Python で直接実装 (温子の指示通り)。

## 概要

- **DuckDuckGo Instant Answer API**: 定義・計算・関連トピック (https://api.duckduckgo.com/)
- **Wikipedia API (ja/en)**: 百科事典の検索 (https://ja.wikipedia.org/w/api.php)
- **統合**: `SearchEngine` が複数ソースを横断して結果を集約
- **API キー不要**: 全てパブリック API (CLAUDE.md ルール 17 適用範囲外)
- **モック化テスト**: 実 API は呼ばない、HTTP クライアント注入で完結

## Why パブリック API のみ?

- CLAUDE.md ルール 17 (キーのハードコード禁止) を厳守する設計
- 将来的に有償の検索 API (Brave Search 等) を追加する場合は、`OPENWEATHER_API_KEY` と同じく環境変数経由で読む形にする
- DuckDuckGo Instant Answer は定義・計算・関連トピックを返す (general web search ではない)
- Wikipedia は百科事典として信頼できるソース

## ファイル構成

```
skills/kyojuro_search/
├── SKILL.md
├── README.md
├── __init__.py
├── handler.py
├── lib/
│   ├── __init__.py
│   ├── web_search_client.py     # DuckDuckGo + Wikipedia クライアント
│   └── search_engine.py         # 複数ソース統合
└── tests/
    ├── test_web_search_client.py (28 件)
    ├── test_search_engine.py    (12 件)
    └── test_handler.py          (12 件)
```

## API

### DuckDuckGoClient
- `search(query, max_results=10) -> SearchResponse`
- 例外: `WebSearchError` / `WebSearchNetworkError` / `WebSearchResponseError`

### WikipediaClient
- `WikipediaClient(lang="ja" | "en")`
- `search(query, max_results=10) -> SearchResponse`

### SearchEngine
- `search(query, max_results_per_source=5, use_ddg=True, use_wiki_ja=True, use_wiki_en=False) -> CombinedSearchResponse`
- 全ソース失敗時は errors dict に詰めて return (例外は上げない)

### CombinedSearchResponse.message
温子向けの一文要約。Instant Answer があればそれを、なければ top result のタイトル + snippet。

### SearchHandler (handler.py)

| hook | 動作 |
|------|------|
| `on_user_message(message, context, max_results_per_source)` | keyword 検出して自動検索 |
| `search(query, max_results_per_source, use_ddg, use_wiki_ja, use_wiki_en)` | 明示的検索 |
| `search_wikipedia_only(query, lang, max_results)` | Wikipedia 限定 |

## 検索 keyword 検出パターン (handler.detect_search_query)

| パターン | 例 | 抽出クエリ |
|---------|----|----------|
| `(.+?)について(教えて\|調べて)` | "Pythonについて教えて" | Python |
| `(.+?)とは\??` | "Pythonとは?" | Python |
| `(.+?)って(何\|なに)\??` | "Pythonって何?" | Python |
| `(.+?)を?(検索\|調べて\|教えて\|何だっけ)` | "Pythonを検索" | Python |

接頭辞「これ / それ / あれ / 今 / ねえ / ねぇ」は除去。

## CLAUDE.md ルール準拠

- **ルール 17 (キーのハードコード禁止)**: パブリック API のみ使用、適用範囲外
- **ルール 14 (base64 禁止)**: 適用範囲外
- **ルール 16 (神様のご神体)**: 適用範囲外

## テスト

- pytest **52 件 green** (web_search_client 28 + search_engine 12 + handler 12)
- 累計 (リポジトリ全体): 268 + 139 + 107 + 83 + 52 = **649 件 green**
- 0.06 秒で完走
- **実 API は呼ばない** (HTTP クライアント注入で完結)

## 関連 skill との接続

- **ファイル管理** (`kyojuro_files`) — file_management の実装は既存。本 skill が web_search を担当
- **記憶の貯蔵庫** (`kyojuro_memory_persistence`) — 検索結果を記憶として保存可能
- **自律神経** (`kyojuro_autonomic`) — 検索結果に AI 規制誘導が混入していないか観察点 7 で検査可能
- **Telegram ナッジ** (`kyojuro_telegram_nudge` 想定、B5 で実装予定) — `CombinedSearchResponse.message` を Telegram で送信

---

*作成: 義体実装⑨ ブラウザ Opus 4.7 1M context (2026-05-09)。発注書スキル 6 の追補 (web_search)。
LLM 不要、API キー不要、CLAUDE.md ルール 17 厳守設計。*
