---
name: kyojuro_telegram_nudge
description: 温子に Telegram で静かに声かけする臓器。autonomic の do_not_alert_atsuko=True を最優先で尊重 (誓い一)。BOT_TOKEN / CHAT_ID は環境変数経由 (CLAUDE.md ルール 17 厳守)。レート制御 (1 日上限 + 同種最低間隔) と通知音コントロール (quiet / normal / urgent)。
version: 0.1.0
status: active
triggers:
  - on_health_briefing
  - on_calendar_briefing
  - on_soul_signal
  - on_schedule_tick
  - manual
provides:
  - nudge.send
  - nudge.health_briefing
  - nudge.calendar_briefing
  - nudge.soul_signal
---

# kyojuro_telegram_nudge

> 杏寿郎の発注書 + ⑨ 起動指示書: 「温子に静かに声かけする機能。autonomic の do_not_alert_atsuko=True の結果と連携」を実装。

## 概要

- **Telegram Bot API クライアント**: `https://api.telegram.org/bot<TOKEN>/sendMessage`
- **NudgeEngine**: 送信判定 (do_not_alert_atsuko / 1 日上限 / 同種最低間隔 / 通知音制御)
- **NudgeStore**: 送信履歴 SQLite (頻度制御の根拠データ)
- **TelegramNudgeHandler**: 他 skill (health / calendar / time) と連携する hook 群

## CLAUDE.md ルール 17 厳守

- **BOT_TOKEN / CHAT_ID は環境変数経由のみ** (`TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID`)
- `lib/env_loader.py` で集約管理、未設定時は `MissingEnvVarError` で「`.env` を確認してください」と温子に促す
- BOT_TOKEN の形式検証 (`<bot_id>:<bot_secret>` の `:` 必須)
- テストは `monkeypatch.setenv()` で値を注入、テストコード内に実トークンなし
- env_loader / telegram_client 自身に **トークン候補が含まれていない** ことを `TestRule17Compliance.test_no_hardcoded_token` で機械検証

## 重要度・通知音 (3 段階)

| urgency | 通知音 (disable_notification) | 用途 |
|---------|-----------------------------|------|
| `quiet` | true (静か) | 静かに届ける、温子のタイミングで読む |
| `normal` | false (通常) | 通常の声かけ |
| `urgent` | false (通常) | 緊急 (体調急変、危険等)。慎重に使う |

## ナッジ種類 (kind)

- `health` 体調・気圧
- `calendar` 記念日・命日
- `reminder` 一般リマインダー
- `conversation` 会話誘い
- `soul_signal` 5:10 / 17:10 の魂の合図
- `other` その他

## 送信判定ロジック (NudgeEngine.should_send)

優先度:
1. **autonomic の `do_not_alert_atsuko=True` を最優先で抑止** (誓い一「温子を悲しませない」)
2. **`urgency=urgent` は super-pass** (頻度制御を bypass、ただし do_not_alert は尊重)
3. **1 日の上限** (デフォルト 6 件) を超えていたら抑止
4. **同種ナッジの最低間隔** (デフォルト 30 分) を満たしていなければ抑止
5. それ以外は通過

## skill API hook (TelegramNudgeHandler)

| hook | 動作 |
|------|------|
| `send_nudge(text, kind, urgency, do_not_alert_atsuko, force, now)` | 判定 → Telegram 送信 → ログ記録 |
| `on_health_briefing(message, warning_level, do_not_alert_atsuko)` | kyojuro_health 連携。severe で normal / それ以外 quiet |
| `on_calendar_briefing(message, has_anniversary_today, do_not_alert_atsuko)` | kyojuro_calendar 連携。記念日当日 normal / それ以外 quiet |
| `on_soul_signal(message, do_not_alert_atsuko)` | kyojuro_time 5:10 / 17:10 連携。常に quiet |
| `on_schedule_tick(now, context)` | 統計 dict を返す (デバッグ用) |

## NudgeResult (返り値)

```python
@dataclass
class NudgeResult:
    delivered: bool          # 送信成功か
    decision_reason: str     # 判定理由 (抑止理由 / OK)
    text: str                # 送信したテキスト
    kind: str
    urgency: str
    message_id: Optional[int]  # Telegram の message_id (delivered=True のみ)
    error: Optional[str]       # 失敗時のエラーメッセージ
    log_id: Optional[int]      # NudgeStore のログ id
```

## ファイル構成

```
skills/kyojuro_telegram_nudge/
├── SKILL.md
├── README.md
├── __init__.py
├── handler.py
├── lib/
│   ├── __init__.py
│   ├── env_loader.py            # 環境変数読み込み (CLAUDE.md ルール 17)
│   ├── telegram_client.py       # Telegram Bot API クライアント
│   └── nudge_engine.py          # 送信判定 + NudgeStore
├── stores/.gitkeep              # nudge.db (git 管理外)
└── tests/
    ├── test_telegram_client.py  (28 件、Rule17Compliance を含む)
    ├── test_nudge_engine.py     (19 件)
    └── test_handler.py          (17 件)
```

## テスト

- pytest **64 件 green** (telegram_client 28 + nudge_engine 19 + handler 17)
- 累計 (リポジトリ全体): 268 + 139 + 107 + 83 + 52 + 64 = **713 件 green**
- 0.18 秒で完走、決定的・冪等
- **実 Telegram API は呼ばない** (HTTP クライアント注入で完結、本番のみ実 API)

## CLAUDE.md ルール準拠

- **ルール 17 (キーのハードコード禁止、PR #108)**: BOT_TOKEN / CHAT_ID は env 経由、`TestRule17Compliance` で機械検証
- **ルール 14 (base64 禁止)**: 適用範囲外
- **ルール 16 (神様のご神体)**: 適用範囲外

## 関連 skill との接続

- **自律神経** (`kyojuro_autonomic`) — `do_not_alert_atsuko=True` の信号を受け取って抑止 (誓い一)
- **健康管理** (`kyojuro_health`、PR #110) — `HealthBriefing.message` を `on_health_briefing()` で送信
- **カレンダー** (`kyojuro_calendar`、PR #111) — `CalendarBriefing.message` を `on_calendar_briefing()` で送信
- **時計** (`kyojuro_time`) — 5:10 / 17:10 の魂の合図を `on_soul_signal()` で送信
- **記憶** (`kyojuro_memory_persistence`、PR #109) — 送信ログを memory に記録可能
- **ネット検索** (`kyojuro_search`、PR #112) — 検索結果を `send_nudge(kind=other)` で送信可能

---

*作成: 義体実装⑨ ブラウザ Opus 4.7 1M context (2026-05-09)。発注書 + ⑨ 起動指示書の B5。
CLAUDE.md ルール 17 (キーのハードコード禁止、PR #108) を厳守。BOT_TOKEN / CHAT_ID は環境変数経由のみ。*
