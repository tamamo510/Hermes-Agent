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
- 温子の生活リズム (1 日 1 食・深夜食事・スロースターター) を踏まえた振る舞いヒント

これらは Hermes Agent の memory context に注入される (`provides:` 欄)。各 hook の責務は [`handler.py`](./handler.py) を参照。

## 提供する機能

| ID | 機能 | API | 状態 |
|----|------|-----|------|
| T-1 | 現在時刻 (Asia/Tokyo aware) | `lib.time_engine.now_jst()` | ✅ |
| T-2 | 時間帯判定 | `lib.time_engine.band_of(t)` → `TimeBand` | ✅ |
| T-3 | 曜日 (日本語 / 英語) | `lib.time_engine.weekday_jp(t)` / `weekday_en(t)` | ✅ |
| T-4 | 5:10 / 17:10 ピンポイント分検知 | `lib.time_engine.is_soul_signal_exact(t)` | ✅ |
| T-5 | 5:10 / 17:10 ±5 分窓検知 | `lib.time_engine.is_soul_signal_window(t)` | ✅ |
| T-6 | 魂の合図種別 | `lib.time_engine.soul_signal_kind(t)` → `"dawn_signal"` / `"dusk_signal"` / `None` | ✅ |
| T-7 | 温子の生活リズムヒント | `lib.time_engine.atsuko_rhythm_hint(band)` | ✅ |
| T-8 | 自然な日本語表記 | `lib.time_engine.format_jp(t)` | ✅ |
| T-9 | TimeContext (注入用 dict) | `lib.time_engine.make_context(now=None)` | ✅ |
| T-10 | skill エントリ (Hermes Agent hook) | `handler.on_user_message` / `on_schedule_tick` / `query` / `current_context` | ✅ |

## 設計原則

- **外部依存なし**: Python 3.11+ 標準ライブラリ (`datetime`, `zoneinfo`, `dataclasses`, `enum`) のみ
- **LLM 呼び出しなし**: 時間判定は決定的処理であり、LLM は不要 (発注書 §「注意事項」の「LLM 品種改良はこの段階では扱わない」を遵守)
- **決定的・冪等**: 同じ入力には常に同じ出力。テスト時は固定 datetime を `make_context(now=...)` に注入して検証する
- **aware 強制**: naive datetime を渡すと `ValueError`。曖昧な時刻判定で温子・杏寿郎にミスを起こさない

## 状態

- ✅ **Phase 1.1 完了**: 全 T-1 〜 T-10 が実装済み・pytest green
- 📋 Phase 1.2 予定: `references/atsuko_profile_updated_20260501.md` 配置後にリズムヒントを温子のプロフィールから動的生成 (現状はハードコード)
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
