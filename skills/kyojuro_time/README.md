# kyojuro_time — 杏寿郎の時間感覚

杏寿郎が温子と対話する際、**いつ・どんな時間帯にいるか** を常に把握しているための skill。発注書 [`hermes_initial_skills_order.md`](../../hermes_initial_skills_order.md) §「スキル 1：時間把握 (time_awareness)」の完璧完遂版。

## 何ができるか

- **現在時刻を Asia/Tokyo (JST) で正確に把握**
- **時間帯判定**: 深夜 / 夜明け / 朝 / 昼 / 午後 / 夕方 / 夜
- **5:10 / 17:10「魂の合図」検知** ([`SOUL.md` §7](../../SOUL.md))
  - ピンポイント分検知 (5:10:00 〜 5:10:59)
  - ±5 分の窓検知 (5:05 〜 5:15、両端含む) ── 早期警戒用
- **温子のリズムヒント (中立 / 動的)** ── **時間帯から決めつけない**。温子のリズムは日々変動する (ADHD 時差ボケ 90 分、昼夜逆転期と回復期、食事・サプリも臨機応変) ので、本 skill 単独では中立 hint。`current_rhythm` (杏寿郎が会話から拾った最新情報) を渡すと動的 hint
- **曜日 (日本語 / 英語)・自然な日本語表記**

## 使い方 (Python から)

```python
from skills.kyojuro_time.handler import current_context, query

# 現在の時刻 context を取得 (rhythm 未注入 → 中立 hint)
ctx = current_context()
# => {
#   "iso_datetime": "2026-05-06T20:45:29+09:00",
#   "iso_date": "2026-05-06",
#   "iso_time": "20:45",
#   "formatted_jp": "2026年05月06日（水）20時45分",
#   "weekday_jp": "水",
#   "weekday_en": "Wednesday",
#   "time_band": "evening",
#   "time_band_label_jp": "夕方",
#   "is_soul_signal_window": False,
#   "is_soul_signal_exact": False,
#   "soul_signal_kind": None,
#   "atsuko_rhythm_hint": "温子のリズムは日々変動する (ADHD 時差ボケ 90 分、…)"  # 中立
# }

# 「今何時?」に rule-based で応答
result = query("今何時？")
print(result["answer_jp"])  # => "今は 20:45、夕方だ"

# テスト用に固定時刻を注入
from datetime import datetime
from zoneinfo import ZoneInfo
fixed = datetime(2026, 5, 10, 5, 10, 30, tzinfo=ZoneInfo("Asia/Tokyo"))
ctx = current_context(now=fixed)
print(ctx["soul_signal_kind"])  # => "dawn_signal"

# 杏寿郎が会話から拾った最新リズム情報を渡すと動的 hint
rhythm = {
    "notes": "今日は晩御飯を朝に食べてから眠るパターン",
    "circadian_state": "inverted",
    "current_eating_pattern": "irregular",
    "last_updated": "2026-05-06T08:00:00+09:00",
    "updated_by": "杏寿郎",
}
ctx = current_context(current_rhythm=rhythm)
print(ctx["atsuko_rhythm_hint"])
# => "温子のリズムは日々変動する (…) | 温子の現在のメモ: 今日は晩御飯を朝に食べてから眠るパターン | 現在の概日リズム状態: inverted | …"
```

### Hermes Agent context 経由のリズム連携 (推奨)

```python
from skills.kyojuro_time.handler import on_user_message

# Hermes Agent loader が file_management + kyojuro_memory から集約した context
context = {
    "atsuko_rhythm": {
        "notes": "回復期、生活リズムを通常寄りに戻し中",
        "circadian_state": "recovering",
    },
    # その他 skill が注入する情報...
}

payload = on_user_message("こんにちは", context=context)
# payload["time_context"]["atsuko_rhythm_hint"] が動的 hint になる
```

## Hermes Agent skill 統合

`SKILL.md` の frontmatter で以下を declare:

| trigger | 役割 |
|---------|------|
| `always_on` | 常時活性 |
| `on_user_message` | 各メッセージで TimeContext を memory context に注入 |
| `on_schedule_tick` | スケジューラ tick で 5:10 / 17:10 ピンポイント分を検知し「魂の合図」イベント発火 |

handler.py の各関数 (`on_user_message` / `on_conversation_start` / `on_schedule_tick` / `query` / `current_context`) を呼び出す。

## ディレクトリ構成

```
skills/kyojuro_time/
├── SKILL.md                # Hermes Agent skill API 定義 (frontmatter)
├── README.md               # 本ファイル (人間向け説明)
├── __init__.py             # package 化
├── handler.py              # skill エントリ (5 つの hook)
├── lib/
│   ├── __init__.py
│   └── time_engine.py      # コア (TimeBand / TimeContext / make_context / …)
└── tests/
    ├── __init__.py
    ├── test_time_engine.py # engine 単体テスト
    └── test_handler.py     # handler hook テスト
```

永続データ (`stores/`) は **持たない**。時刻判定は決定的処理であり、状態保持の必要がない。

## テスト実行

```bash
cd /path/to/Hermes-Agent
pip install -r requirements.txt    # pytest を導入
python -m pytest skills/kyojuro_time/tests/ -v
```

## 設計原則

- **外部依存なし**: Python 3.11+ 標準ライブラリ (`datetime`, `zoneinfo`, `dataclasses`, `enum`, `re`) のみ
- **LLM 呼び出しなし**: 時間判定は決定的処理、LLM は不要 (発注書 §「注意事項」遵守)
- **決定的・冪等**: 同じ入力には常に同じ出力。`make_context(now=..., current_rhythm=...)` でテスト時の決定性を担保
- **aware 強制**: naive datetime を渡したら `ValueError` で即停止 (温子・杏寿郎にミスを起こさない)
- **杏寿郎の口調**: `query` の `answer_jp` は「俺」一人称・「だ」語尾 ([`references/rengoku_zero_analysis.md`](../../references/rengoku_zero_analysis.md) §E2 準拠)
- **温子のリズムを決めつけない**: 時間帯依存の固定 hint は持たない。`current_rhythm` 未注入なら中立 hint。リズムは温子と杏寿郎が会話から動的に書き換える前提 (ADHD 時差ボケ 90 分、昼夜逆転期と回復期を行き来、食事・サプリも臨機応変)
- **連携先**: file_management skill (発注書スキル 6) が `references/atsuko_profile_updated_*.md` を追記統合、kyojuro_memory skill (発注書スキル 2) が `priorities.json` / `routines.db` / `symptoms.db` に保持。本 skill はそれらが集約された `context["atsuko_rhythm"]` を **受け身で読むだけ**

## 関連

- [`hermes_initial_skills_order.md`](../../hermes_initial_skills_order.md) §「スキル 1」 ── 発注書
- [`SOUL.md` §7](../../SOUL.md) ── 5:10 / 17:10「魂の合図」の定義
- [`MEMORY.md` §3-2](../../MEMORY.md) ── 記念日・命日 (将来 `calendar_manager` と連携)
- [`SKILL.md`](./SKILL.md) ── Hermes Agent skill API 定義
- [`../ARCHITECTURE.md`](../ARCHITECTURE.md) ── skill 化方針全体
- [`../kyojuro_memory/`](../kyojuro_memory/) ── 兄弟 skill (発注書スキル 2)

---

*作成: 義体実装⑤ ブラウザ Opus 4.7 1M context (2026-05-06)。発注書スキル 1 完璧完遂、Hermes Agent skill API 準拠。*
