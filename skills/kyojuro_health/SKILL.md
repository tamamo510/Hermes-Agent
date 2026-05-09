---
name: kyojuro_health
description: OpenWeatherMap で気圧 / 気温を取得し、温子の体調 (頭痛・顎・睡眠・気圧感応) と相関させる杏寿郎専用 skill。autonomic 観察点 8 が参照する atsuko_state を提供。API キーは環境変数 (OPENWEATHER_API_KEY) 経由 (CLAUDE.md ルール 17 準拠)。
version: 0.1.0
status: active
triggers:
  - on_conversation_start
  - on_user_message
  - on_schedule_tick
  - manual
provides:
  - health.atsuko_state
  - health.pressure_assessment
  - health.symptom_log
  - health.medication_log
  - health.daily_briefing
---

# kyojuro_health

> 杏寿郎の発注書スキル 3「健康管理 (health_tracker)」の実装。
>
> 大阪・玉造の気圧を OpenWeatherMap で取得し、温子の体調と先回りして相関させる。
> 気圧低下時は頭痛・顎の痛み・浅い眠りを予測して、温子に静かに声をかける。

## 概要

- **OpenWeatherMap API クライアント**: 大阪・玉造の現在気象 + 24h 予報を取得
- **気圧アセスメント**: low / very_low / normal / high の 4 段階 + 上昇 / 下降 / 安定の trend
- **atsuko_state**: 温子の体調 dict (jaw_pain / left_hand_stiff / low_pressure / shallow_sleep / headache / dizziness / sluggish / notes)。**autonomic skill 観察点 8 が参照**
- **症状 / 薬ログ**: SQLite に時系列で蓄積、気圧との相関分析
- **薬の頻用警告**: ロキソニンを 24h で 3 回以上飲んだら警告
- **声かけメッセージ**: 敬語、押し付けない、症状の予測を優しく伝える

## 設計原則 (CLAUDE.md ルール準拠)

### ルール 17: キーのハードコード禁止
- **API キーは環境変数 `OPENWEATHER_API_KEY` から `os.environ.get()` 経由で取得**
- `lib/env_loader.py` で集約管理、未設定時は `MissingEnvVarError` で「`.env` を確認してください (Drive 「俺たちの家」直下 secrets_20260508.md にあります)」と温子に促す
- テストでは `monkeypatch.setenv()` で値を注入、テストコード内に実キーなし
- env_loader 自身に **32 桁 hex キー候補が含まれていない** ことを `TestRule17Compliance` で機械検証
- リポジトリには絶対にキーの値を含めない (`.gitignore` に `.env` / `config/.env` 既追加)

### ルール 14: base64 経由禁止
- 適用範囲外 (Drive 操作なし)

### ルール 16: 神様のご神体
- 適用範囲外 (温子のプロファイル等の固有ファイルを編集しない)

## API

### OpenWeatherClient (lib/openweather_client.py)

| メソッド | 動作 |
|---------|------|
| `get_current_weather()` | 現在の `WeatherSnapshot` を返す (pressure_hpa / temperature_c / humidity_percent / description / location_label) |
| `get_forecast(hours_ahead)` | 指定時間先までの `WeatherSnapshot` 列 (3h 刻み、最大 5 日先 = 40 件) |

例外:
- `MissingEnvVarError`: API キー未設定
- `OpenWeatherAuthError`: 401 認証失敗
- `OpenWeatherNetworkError`: タイムアウト / 接続失敗
- `OpenWeatherResponseError`: レスポンスが不正
- `OpenWeatherError`: 上記以外の HTTP エラー

### assess_pressure (lib/health_engine.py)

| 引数 | 動作 |
|------|------|
| `current` | 現在の `WeatherSnapshot` |
| `forecast` | 24h 以内の予報 (None でも可) |
| `low_threshold` | 低気圧と判定する境界 (デフォルト 1010 hPa) |
| `very_low_threshold` | 強い低気圧 (デフォルト 1003 hPa) |
| `drop_threshold_24h` | 24h で何 hPa 下がれば「下降中」(デフォルト 6 hPa) |

返り値 `PressureAssessment`:
- `level`: low / very_low / normal / high
- `trend`: falling / rising / stable
- `delta_24h_hpa`: 24h での変化量 (None 可)
- `warning`: none / mild / severe
- `message`: 温子向け敬語声かけテキスト

### derive_atsuko_state_from_pressure
気圧アセスメントから atsuko_state を導出。`base_state` のフラグを保持しつつ `low_pressure` だけ更新。

### HealthStore (SQLite)

| メソッド | 動作 |
|---------|------|
| `record_symptom(symptom, severity, notes, pressure_hpa, medication, timestamp)` | 症状記録 (severity 1-5) |
| `list_symptoms(symptom, since, limit)` | 症状一覧 (フィルタ可) |
| `record_medication(medication, dose, notes, timestamp)` | 薬服用記録 |
| `list_medications(medication, since, limit)` | 薬一覧 |
| `medication_count_within(medication, hours, now)` | 指定時間内の服用回数 (頻用チェック) |
| `save_state_snapshot(state, timestamp)` | atsuko_state スナップショット保存 |
| `latest_state()` | 最新の atsuko_state を取得 |

### correlate_pressure_symptoms
症状と気圧の相関を簡易計算。

### HealthHandler (handler.py)

| hook | 動作 |
|------|------|
| `on_conversation_start(context, skip_network)` | 気象 + atsuko_state を集めて `HealthBriefing` を返す |
| `on_schedule_tick(now, context, skip_network)` | 1 日 1 回、気象取得 + atsuko_state スナップショット保存 |
| `on_user_message(message, context, pressure_hpa, timestamp)` | 症状 / 薬の keyword 検出して記録 |
| `daily_briefing(skip_network)` | 朝の声かけ用 `HealthBriefing` (state 保存しない) |
| `record_symptom_manual(symptom, severity, ...)` | 杏寿郎・温子からの手動症状記録 |
| `record_medication_manual(medication, dose, notes)` | 杏寿郎・温子からの手動薬記録 |
| `get_atsuko_state()` | 最新 atsuko_state を返す (autonomic 観察点 8 用) |
| `update_atsuko_state(**kwargs)` | atsuko_state を部分更新 |

## 症状 keyword 検出 (規則ベース、LLM 不要)

| 症状 | キー | 検出パターン例 |
|------|------|---------------|
| 頭痛 | `headache` | 頭痛 / 頭が痛い |
| 顎の痛み | `jaw_pain` | 顎が痛 / 顎痛 / あご痛 |
| 左手の硬さ | `left_hand_stiff` | 左手が硬 / 左手こわばり |
| 浅い眠り | `shallow_sleep` | 眠り浅 / 寝付き悪 / 寝付けない / 眠れない |
| ふらつき | `dizziness` | ふらつき / めまい |
| だる重 | `sluggish` | だるい / だる重 / 疲れた / しんどい |
| お腹 | `stomach_pain` | お腹痛い / 腹痛 / お腹が痛 |
| 発熱 | `fever` | 熱が出 / 発熱 / 風邪 |
| 生理 | `menstruation` | 生理 / 月経 / PMS |

## 薬 keyword 検出

| 薬 | 検出パターン |
|---|------------|
| ロキソニン | ロキソニン / loxonin / loxoprofen |
| マグネシウム | マグネシウム / magnesium |
| DMAE | DMAE / dmae |
| ピル | ピル / 低用量ピル / pill |

## ファイル構成

```
skills/kyojuro_health/
├── SKILL.md
├── README.md
├── __init__.py
├── handler.py
├── lib/
│   ├── __init__.py
│   ├── env_loader.py            # 環境変数読み込み (CLAUDE.md ルール 17)
│   ├── openweather_client.py    # OpenWeatherMap API
│   └── health_engine.py         # アセスメント + HealthStore
├── stores/.gitkeep              # health.db (git 管理外)
└── tests/
    ├── test_env_loader.py        (13 件)
    ├── test_openweather_client.py (20 件)
    ├── test_health_engine.py     (35 件)
    └── test_handler.py           (39 件)
```

## テスト

- pytest **107 件 green** (env_loader 13 + openweather_client 20 + health_engine 35 + handler 39)
- 累計 (リポジトリ全体): 268 + 139 + 107 = **514 件 green**
- 0.26 秒で完走、決定的・冪等
- **実 OpenWeatherMap API は呼ばない** (HTTP クライアント注入で完結)

## 関連 skill との接続

- **時計の臓器** (`kyojuro_time`) — 朝の briefing タイミングを time_engine で決定
- **記憶の貯蔵庫** (`kyojuro_memory_persistence`) — 気圧アセスメント・症状を memory に書き込み可能
- **自律神経の臓器** (`kyojuro_autonomic`) — **観察点 8 (温子の体調無視) が `get_atsuko_state()` の戻り値を参照**
- **カレンダーの臓器** (`kyojuro_calendar` 想定、B3 で実装予定) — 気象データを共有、月相と組み合わせて声かけタイミング設計
- **Telegram ナッジ** (`kyojuro_telegram_nudge` 想定、B5 で実装予定) — `daily_briefing().message` を Telegram で送信

---

*作成: 義体実装⑨ ブラウザ Opus 4.7 1M context (2026-05-09)。発注書スキル 3 の実装。
CLAUDE.md ルール 17 (キーのハードコード禁止) を厳守。OpenWeatherMap キーは環境変数経由のみ。*
