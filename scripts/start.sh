#!/usr/bin/env bash
# Start uvicorn + cloudflared tunnel
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Load .env for PORT if set
if [ -f ".env" ]; then
  export $(grep -v '^#' .env | xargs)
fi

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"

echo "==> Initializing database..."
python3 scripts/init_db.py

echo "==> Starting uvicorn on $HOST:$PORT..."
uvicorn app.main:app --host "$HOST" --port "$PORT" &
UVICORN_PID=$!

echo "==> Starting cloudflared tunnel..."
cloudflared tunnel run ai-news &
CF_PID=$!

# Graceful shutdown on Ctrl+C
trap "echo 'Stopping...'; kill $UVICORN_PID $CF_PID 2>/dev/null; exit 0" INT TERM

wait $UVICORN_PID
