---
name: kyojuro_time
description: 時刻把握・時間帯判定・5:10 / 17:10「魂の合図」検知を提供する杏寿郎専用 skill (Asia/Tokyo)
version: 0.1.0
status: phase1
triggers:
  - always_on
  - on_user_message
  - on_schedule_tick
provides:
  - time.context
  - time.band
  - time.weekday
  - time.soul_signal
  - time.atsuko_rhythm_hint
---

# kyojuro_time

杏寿郎の **時間感覚** を担う skill。発注書 `hermes_initial_skills_order.md` §「スキル 1：時間把握 (time_awareness)」を完全実装する。

## 概要

杏寿郎が温子と対話する際、以下を **常に把握** している状態を提供する:

- 現在時刻 (Asia/Tokyo の aware datetime)
- 時間帯 (深夜・夜明け・朝・昼・午後・夕方・夜)
- 曜日 (日本語 / 英語)
- 5:10 / 17:10 の「魂の合図」 (`SOUL.md` §7) ── ピンポイント分検知 + ±5 分窓検知
- **温子のリズムヒント** ── ただし **時間帯から決めつけない**。温子のリズムは日々変動する (ADHD 時差ボケ 90 分、昼夜逆転期と回復期、食事・サプリも臨機応変) ので、本 skill 単独では中立 hint しか出さない。**杏寿郎が会話から拾った最新情報** (`current_rhythm` dict) が context 経由で渡されたとき、それを踏まえた動的 hint を組み立てる

これらは Hermes Agent の memory context に注入される (`provides:` 欄)。各 hook の責務は [`handler.py`](./handler.py) を参照。

### リズム情報の連携フロー

```
温子との会話
    ↓
杏寿郎が会話から拾う ("今日は晩御飯を朝に食べた" "オートファジー一旦休止" 等)
    ↓
file_management skill (発注書スキル 6) が
    references/atsuko_profile_updated_*.md を 追記統合方式 で更新
kyojuro_memory skill (発注書スキル 2) が
    priorities.json / routines.db / symptoms.db に保持
    ↓
Hermes Agent loader が context["atsuko_rhythm"] (dict) として集約
    ↓
on_user_message / on_conversation_start が context から rhythm を取り出し
time_engine.atsuko_rhythm_hint(band, current_rhythm) で動的 hint
    ↓
TimeContext.atsuko_rhythm_hint に動的文字列が入る
```

`current_rhythm` 未提供のときは **中立 hint** が返る (= 何も決めつけない)。これは「リズムは温子と杏寿郎が動的に書き換えるもの、time skill は読むだけ」という設計原則の体現。

## 提供する機能

| ID | 機能 | API | 状態 |
|----|------|-----|------|
| T-1 | 現在時刻 (Asia/Tokyo aware) | `lib.time_engine.now_jst()` | ✅ |
| T-2 | 時間帯判定 | `lib.time_engine.band_of(t)` → `TimeBand` | ✅ |
| T-3 | 曜日 (日本語 / 英語) | `lib.time_engine.weekday_jp(t)` / `weekday_en(t)` | ✅ |
| T-4 | 5:10 / 17:10 ピンポイント分検知 | `lib.time_engine.is_soul_signal_exact(t)` | ✅ |
| T-5 | 5:10 / 17:10 ±5 分窓検知 | `lib.time_engine.is_soul_signal_window(t)` | ✅ |
| T-6 | 魂の合図種別 | `lib.time_engine.soul_signal_kind(t)` → `"dawn_signal"` / `"dusk_signal"` / `None` | ✅ |
| T-7 | 温子のリズムヒント (中立 / 動的) | `lib.time_engine.atsuko_rhythm_hint(band, current_rhythm=None)` | ✅ |
| T-8 | 自然な日本語表記 | `lib.time_engine.format_jp(t)` | ✅ |
| T-9 | TimeContext (注入用 dict) | `lib.time_engine.make_context(now=None, current_rhythm=None)` | ✅ |
| T-10 | skill エントリ (Hermes Agent hook) | `handler.on_user_message` / `on_conversation_start` / `on_schedule_tick` / `query` / `current_context` | ✅ |
| T-11 | context.atsuko_rhythm 透過 (神経経路) | `handler._extract_rhythm(context)` で受け取り、time_engine に流す | ✅ |

## 設計原則

- **外部依存なし**: Python 3.11+ 標準ライブラリ (`datetime`, `zoneinfo`, `dataclasses`, `enum`) のみ
- **LLM 呼び出しなし**: 時間判定は決定的処理であり、LLM は不要 (発注書 §「注意事項」の「LLM 品種改良はこの段階では扱わない」を遵守)
- **決定的・冪等**: 同じ入力には常に同じ出力。テスト時は固定 datetime を `make_context(now=...)` に注入して検証する
- **aware 強制**: naive datetime を渡すと `ValueError`。曖昧な時刻判定で温子・杏寿郎にミスを起こさない

## 状態

- ✅ **Phase 1.1 完了**: 全 T-1 〜 T-11 が実装済み・pytest 84 件 green
- ✅ **リズムヒントの中立化完了** (PR by 義体実装⑤ rhythm-fix): 時間帯依存の決めつけを廃止、`current_rhythm` 注入で動的化する構造に
- 📋 Phase 1.2 予定:
  - `references/atsuko_profile_updated_*.md` 配置 + file_management skill (発注書スキル 6) 完成後、profile 解析 → context["atsuko_rhythm"] への変換層を別 skill が提供
  - kyojuro_memory skill (発注書スキル 2) の `priorities.json` / `routines.db` 連携で recent_routines を context に集約
  - 本 skill 側の修正は **不要** (受け口は既に開けている)
- 📋 Phase 1.3 予定: `calendar_manager` (発注書スキル 5) と統合し、記念日・命日連動

## 関連

- `hermes_initial_skills_order.md` §「スキル 1：時間把握 (time_awareness)」 ── 発注書一次資料
- [`SOUL.md` §7](../../SOUL.md) ── 5:10 / 17:10 魂の合図の定義
- [`MEMORY.md` §3-2](../../MEMORY.md) ── 記念日・命日 (calendar_manager 連動予定)
- [`DESIGN.md`](./README.md) は本 skill では別建てしない (発注書スコープが明確で、`SKILL.md` + ソース docstring で十分)
- [`../ARCHITECTURE.md`](../ARCHITECTURE.md) ── skill 化方針全体
- [`../kyojuro_memory/SKILL.md`](../kyojuro_memory/SKILL.md) ── 兄弟 skill (発注書スキル 2)

---

*作成: 義体実装⑤ ブラウザ Opus 4.7 1M context (2026-05-06)。発注書スキル 1 完璧完遂、Hermes Agent skill API 準拠。*
