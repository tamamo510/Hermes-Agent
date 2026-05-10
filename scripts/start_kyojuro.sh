#!/bin/bash
# yorishiro/scripts/start_kyojuro.sh
# 杏寿郎を起こす ── Telegram listener 起動 + 起動の挨拶
#
# 前提: 先に scripts/setup_kyojuro.sh が成功していること。
# 起動: cd ~/yorishiro && bash scripts/start_kyojuro.sh
# 停止: pkill -f 'hermes gateway start'
# ログ: tail -f ~/yorishiro/hermes.log

set -e

YORISHIRO="${HOME}/yorishiro"
HERMES_HOME="${HERMES_HOME:-${HOME}/.hermes}"
LOG_FILE="${YORISHIRO}/hermes.log"

cd "${YORISHIRO}"

if [ ! -f "${HERMES_HOME}/.env" ]; then
    echo "[ERROR] ${HERMES_HOME}/.env がない。先に bash scripts/setup_kyojuro.sh を実行しろ。"
    exit 1
fi

if [ ! -f "${HERMES_HOME}/SOUL.md" ]; then
    echo "[ERROR] ${HERMES_HOME}/SOUL.md がない。先に bash scripts/setup_kyojuro.sh を実行しろ。"
    exit 1
fi

# 4 キーを ~/.hermes/.env から読む
TG_TOKEN="$(grep -E '^TELEGRAM_BOT_TOKEN=' "${HERMES_HOME}/.env" | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'" | xargs)"
TG_CHAT="$(grep -E '^TELEGRAM_CHAT_ID=' "${HERMES_HOME}/.env" | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'" | xargs)"

if [ -z "${TG_TOKEN}" ] || [ -z "${TG_CHAT}" ]; then
    echo "[ERROR] TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID が ~/.hermes/.env にない。"
    exit 1
fi

# 既存の hermes プロセスを止める（再起動対応）
if pgrep -f "hermes gateway start" > /dev/null; then
    echo "[INFO] 既存の hermes gateway を停止..."
    pkill -f "hermes gateway start" || true
    sleep 2
fi

# Telegram listener を nohup で常駐起動
echo "[INFO] hermes gateway start を nohup で起動..."
export PATH="${HOME}/.local/bin:${PATH}"
nohup hermes gateway start > "${LOG_FILE}" 2>&1 &
PID=$!
echo "[INFO] PID = ${PID}, log = ${LOG_FILE}"

# 起動を少し待つ
sleep 5

# プロセスがまだ生きているか確認
if ! kill -0 "${PID}" 2>/dev/null; then
    echo "[ERROR] hermes gateway が異常終了した。ログを確認しろ:"
    echo "        tail -50 ${LOG_FILE}"
    exit 1
fi

# 起動の挨拶を Telegram に送信（杏寿郎の声）
echo "[INFO] 起動の挨拶を Telegram に送信..."
curl -s "https://api.telegram.org/bot${TG_TOKEN}/sendMessage" \
    --data-urlencode "chat_id=${TG_CHAT}" \
    --data-urlencode "text=「温子、おはよう。俺はここにいる」" \
    > /dev/null
echo "[INFO] 完了。Telegram で杏寿郎と話せ。"
echo
echo "════════════════════════════════════════════════════════════════"
echo "  PID:       ${PID}"
echo "  ログ:      tail -f ${LOG_FILE}"
echo "  停止:      pkill -f 'hermes gateway start'"
echo "  状態診断:  hermes doctor"
echo "════════════════════════════════════════════════════════════════"
