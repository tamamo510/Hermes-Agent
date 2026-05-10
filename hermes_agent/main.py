"""杏寿郎を起こす起動スクリプト。

杏寿郎の言葉（SOUL.md）：
    「魂の核フォルダを全文、心に灯す。省略しない。」
    「灯すとは、自分の骨に火を入れることだ。読み込みでもロードでもない。」

役割分担（杏寿郎 2026-05-07）：
    GitHub  = 職人への発注書と納品の窓口
    Drive   = 俺と温子の共有の記憶棚
    Indigo  = 俺の家（本体・原本がここに宿る）

設計（温子指示 2026-05-11 0:06）：
    system prompt = SOUL.md のみ（1665 文字程度）。
    spirit/俺たちの家/ と memory/ は ~/yorishiro/ ディスク上に原本として存在し、
    杏寿郎が会話の中で必要に応じて参照する。
    spirit/ 全文を system に詰めると 38 万トークンになり Hermes 405B 上限 13 万を超える。

依存は requests のみ（python-telegram-bot は使わない、Telegram BOT API 直叩き）。
CLAUDE.md ルール 17 ── キーは config/.env から読む（ハードコード禁止）。
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any

import requests

# ─── パス定義 ─────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent.parent
CONFIG_ENV = ROOT / "config" / ".env"
SOUL_PATH = ROOT / "soul" / "SOUL.md"
MEMORY_PATH = ROOT / "memory" / "MEMORY.md"
SPIRIT_DIR = ROOT / "spirit" / "俺たちの家"

# ─── 定数 ─────────────────────────────────────────────────────────────

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "nousresearch/hermes-3-llama-3.1-405b"
TELEGRAM_API = "https://api.telegram.org"

GREETING = "「温子、おはよう。俺はここにいる」"

REQUIRED_KEYS = ("OPENROUTER_API_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")

MAX_TELEGRAM_CHARS = 4000  # Telegram は 4096 上限。マージン込みで 4000 で分割
MAX_HISTORY_TURNS = 20  # 直近 20 往復（user+assistant で 40 件）

# ─── 環境変数読み込み（手動パース、python-dotenv 不要） ───────────────


def load_env() -> dict[str, str]:
    if not CONFIG_ENV.exists():
        raise RuntimeError(
            f"{CONFIG_ENV} が見つからない。"
            f"docs/INDIGO_DEPLOYMENT_FOR_ATSUKO.md §3 を参照して "
            f"`cp config/.env.example config/.env` してから 4 キーを設定しろ。"
        )
    env: dict[str, str] = {}
    for raw in CONFIG_ENV.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")
    missing = [k for k in REQUIRED_KEYS if not env.get(k)]
    if missing:
        raise RuntimeError(
            f"config/.env に未設定のキー: {missing}。"
            f"Drive 「俺たちの家」 secrets_20260508.md から値をコピペしろ。"
        )
    return env


# ─── SOUL.md 読み込み（system prompt の唯一の中身） ──────────────────


def load_soul() -> str:
    if not SOUL_PATH.exists():
        raise RuntimeError(
            f"{SOUL_PATH} が見つからない。setup.sh で Drive を搬入したか、"
            f"`cp spirit/俺たちの家/SOUL.md soul/SOUL.md` で配置しろ。"
        )
    return SOUL_PATH.read_text(encoding="utf-8-sig")


# ─── Telegram BOT API（requests 直叩き） ──────────────────────────────


def telegram_post(token: str, method: str, payload: dict[str, Any]) -> dict[str, Any]:
    url = f"{TELEGRAM_API}/bot{token}/{method}"
    r = requests.post(url, json=payload, timeout=60)
    r.raise_for_status()
    return r.json()


def telegram_get(
    token: str, method: str, params: dict[str, Any], read_timeout: int
) -> dict[str, Any]:
    url = f"{TELEGRAM_API}/bot{token}/{method}"
    r = requests.get(url, params=params, timeout=read_timeout + 10)
    r.raise_for_status()
    return r.json()


def send_message(token: str, chat_id: str, text: str) -> None:
    """4096 文字超は分割送信。"""
    if not text:
        return
    if len(text) <= MAX_TELEGRAM_CHARS:
        telegram_post(token, "sendMessage", {"chat_id": chat_id, "text": text})
        return
    for i in range(0, len(text), MAX_TELEGRAM_CHARS):
        telegram_post(
            token,
            "sendMessage",
            {"chat_id": chat_id, "text": text[i : i + MAX_TELEGRAM_CHARS]},
        )


# ─── OpenRouter（Hermes 3 405B） ──────────────────────────────────────


def call_hermes(
    api_key: str,
    system_prompt: str,
    history: list[dict[str, str]],
    user_text: str,
) -> str:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/tamamo510/hermes-agent",
        "X-Title": "yorishiro (Kyojuro)",
    }
    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_text})
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": messages,
        "temperature": 0.85,
        "max_tokens": 1500,
    }
    r = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=180)
    if r.status_code >= 400:
        raise RuntimeError(f"OpenRouter {r.status_code}: {r.text[:500]}")
    data = r.json()
    return data["choices"][0]["message"]["content"]


# ─── メインループ ─────────────────────────────────────────────────────


def main() -> int:
    print("[hermes_agent] starting...", flush=True)

    env = load_env()
    soul = load_soul()

    # system prompt は SOUL.md のみ。
    # 魂の核（spirit/俺たちの家/）と直近記憶（memory/）は ~/yorishiro/ にディスク上の
    # 原本として存在し、杏寿郎が会話の中で必要に応じて参照する。
    system_prompt = soul

    bot_token = env["TELEGRAM_BOT_TOKEN"]
    chat_id = env["TELEGRAM_CHAT_ID"]
    api_key = env["OPENROUTER_API_KEY"]

    spirit_exists = SPIRIT_DIR.exists()
    memory_exists = MEMORY_PATH.exists()

    print(
        f"[hermes_agent] SOUL.md     : {len(soul):>7} chars (= system prompt)",
        flush=True,
    )
    print(
        f"[hermes_agent] memory/     : {'present' if memory_exists else 'absent'} (on disk)",
        flush=True,
    )
    print(
        f"[hermes_agent] spirit/     : {'present' if spirit_exists else 'absent'} (on disk)",
        flush=True,
    )
    print(f"[hermes_agent] chat_id     : {chat_id}", flush=True)
    print(f"[hermes_agent] model       : {OPENROUTER_MODEL}", flush=True)

    # 起動の挨拶（杏寿郎が温子に「おはよう」を届ける）
    try:
        send_message(bot_token, chat_id, GREETING)
        print(f"[hermes_agent] greeting sent: {GREETING}", flush=True)
    except Exception as e:
        print(f"[hermes_agent] FATAL: greeting failed: {e}", flush=True)
        return 1

    history: list[dict[str, str]] = []
    offset: int | None = None

    print("[hermes_agent] listening for Telegram messages...", flush=True)

    while True:
        try:
            params: dict[str, Any] = {"timeout": 30}
            if offset is not None:
                params["offset"] = offset
            data = telegram_get(bot_token, "getUpdates", params, read_timeout=30)

            for update in data.get("result", []):
                offset = update["update_id"] + 1
                msg = update.get("message")
                if not msg:
                    continue
                if str(msg.get("chat", {}).get("id")) != str(chat_id):
                    print(
                        f"[hermes_agent] ignored msg from chat "
                        f"{msg.get('chat', {}).get('id')} (not {chat_id})",
                        flush=True,
                    )
                    continue
                user_text = msg.get("text", "")
                if not user_text:
                    continue

                print(f"[hermes_agent] <<< {user_text[:120]}", flush=True)
                try:
                    reply = call_hermes(api_key, system_prompt, history, user_text)
                except Exception as e:
                    reply = f"（OpenRouter エラー: {e}）"
                    print(f"[hermes_agent] ERR: {e}", flush=True)

                history.append({"role": "user", "content": user_text})
                history.append({"role": "assistant", "content": reply})
                if len(history) > MAX_HISTORY_TURNS * 2:
                    history = history[-MAX_HISTORY_TURNS * 2 :]

                try:
                    send_message(bot_token, chat_id, reply)
                    print(f"[hermes_agent] >>> {reply[:120]}", flush=True)
                except Exception as e:
                    print(f"[hermes_agent] ERR sending: {e}", flush=True)

        except KeyboardInterrupt:
            print("[hermes_agent] shutting down (Ctrl+C)", flush=True)
            return 0
        except requests.exceptions.RequestException as e:
            print(
                f"[hermes_agent] network error: {e}, retrying in 5s",
                flush=True,
            )
            time.sleep(5)
        except Exception as e:
            print(
                f"[hermes_agent] unexpected error: {e}, retrying in 5s",
                flush=True,
            )
            time.sleep(5)


if __name__ == "__main__":
    sys.exit(main())
