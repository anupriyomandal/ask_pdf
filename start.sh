#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# start.sh
# Starts both the FastAPI backend and the Telegram bot together.
#
# • FastAPI runs in the foreground bound to $PORT (Railway injects this).
# • Telegram bot runs in the background.
# • If either process exits, the other is killed so Railway restarts cleanly.
# ─────────────────────────────────────────────────────────────

set -euo pipefail

PORT="${PORT:-8000}"

echo "==> Starting FastAPI backend on port ${PORT}…"
uvicorn app:app --host 0.0.0.0 --port "${PORT}" &
BACKEND_PID=$!

# Give the backend a moment to bind before the bot starts making requests to it
sleep 2

echo "==> Starting Telegram bot…"
python3 telegram_bot.py &
BOT_PID=$!

echo "==> Both services running. Backend PID=${BACKEND_PID}, Bot PID=${BOT_PID}"

# Wait for either process to exit; then kill the other and exit with its code
wait -n
EXIT_CODE=$?

echo "==> A process exited with code ${EXIT_CODE}. Shutting down remaining services…"
kill "${BACKEND_PID}" "${BOT_PID}" 2>/dev/null || true

exit "${EXIT_CODE}"
