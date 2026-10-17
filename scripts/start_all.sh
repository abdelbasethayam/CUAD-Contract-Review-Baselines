#!/usr/bin/env bash
set -e
ROOT=/home/jovyan/CUAD-Contract-Review-Baselines
cd "$ROOT"

if curl -sf http://127.0.0.1:8000/health >/dev/null 2>&1; then
  echo "Backend already running on port 8000."
else
  source "$ROOT/.venv/bin/activate"
  nohup uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 >/tmp/cuad_backend.log 2>&1 &
  echo "Started backend (logs: /tmp/cuad_backend.log)"
fi

if curl -sf http://127.0.0.1:5173/ >/dev/null 2>&1; then
  echo "Frontend already running on port 5173."
else
  nohup npm --prefix "$ROOT/frontend" run dev -- --host 0.0.0.0 >/tmp/cuad_frontend.log 2>&1 &
  echo "Started frontend (logs: /tmp/cuad_frontend.log)"
fi

echo "CUAD Contract Review is available on port 5173."
