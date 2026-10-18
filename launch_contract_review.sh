#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
BASE_PATH="/"
BACKEND_URL="http://127.0.0.1:8000/health"
FRONTEND_URL="http://127.0.0.1:5173/"
LOG_DIR="/tmp"

command -v curl >/dev/null || { echo "ERROR: curl is required." >&2; exit 1; }
[[ -x "$ROOT/.venv/bin/python" ]] || { echo "ERROR: Python environment missing at $ROOT/.venv/bin/python" >&2; exit 1; }
[[ -x "$ROOT/frontend/node_modules/.bin/vite" ]] || { echo "ERROR: Frontend dependencies are missing. Run: cd frontend && npm install" >&2; exit 1; }

if ! curl -fsS --max-time 2 "$BACKEND_URL" >/dev/null 2>&1; then
  if (echo >/dev/tcp/127.0.0.1/8000) >/dev/null 2>&1; then
    echo "ERROR: Port 8000 is occupied, but the backend health check failed. See $LOG_DIR/cuad-uvicorn.log" >&2
    exit 1
  fi
  echo "Starting backend on port 8000..."
  nohup "$ROOT/.venv/bin/python" -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 > "$LOG_DIR/cuad-uvicorn.log" 2>&1 < /dev/null &
else
  echo "Backend is already healthy on port 8000."
fi

if ! curl -fsS --max-time 2 "$FRONTEND_URL" >/dev/null 2>&1; then
  if (echo >/dev/tcp/127.0.0.1/5173) >/dev/null 2>&1; then
    echo "ERROR: Port 5173 is occupied, but the frontend root URL failed. See $LOG_DIR/cuad-frontend-5173.log" >&2
    exit 1
  fi
  echo "Starting frontend on port 5173 with a root base path..."
  nohup env CONTRACT_REVIEW_BASE_PATH="/" PORT=5173 npm --prefix "$ROOT/frontend" run dev -- --host 0.0.0.0 --port 5173 --strictPort > "$LOG_DIR/cuad-frontend-5173.log" 2>&1 < /dev/null &
else
  echo "Frontend is already responding on port 5173."
fi

ready=0
for _ in $(seq 1 30); do
  backend_ok=0; frontend_ok=0
  curl -fsS --max-time 2 "$BACKEND_URL" >/dev/null 2>&1 && backend_ok=1 || true
  curl -fsS --max-time 2 "$FRONTEND_URL" >/dev/null 2>&1 && frontend_ok=1 || true
  if [[ "$backend_ok" == 1 && "$frontend_ok" == 1 ]]; then ready=1; break; fi
  sleep 1
done

if [[ "$ready" != 1 ]]; then
  echo "ERROR: App did not become ready within 30 seconds. Recent logs:" >&2
  tail -30 "$LOG_DIR/cuad-uvicorn.log" 2>/dev/null || true
  tail -30 "$LOG_DIR/cuad-frontend-5173.log" 2>/dev/null || true
  exit 1
fi

echo
echo "SUCCESS: Backend and frontend are running."
echo "APP_URL=$FRONTEND_URL"
echo "Backend health: $BACKEND_URL"
echo "Backend log: $LOG_DIR/cuad-uvicorn.log"
echo "Frontend log: $LOG_DIR/cuad-frontend-5173.log"
echo "Open the APP_URL above in the server browser."

