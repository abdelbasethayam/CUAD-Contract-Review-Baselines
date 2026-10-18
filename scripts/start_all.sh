#!/usr/bin/env bash
set -euo pipefail
ROOT=/home/jovyan/CUAD-Contract-Review-Baselines
cd "$ROOT"

if curl -sf http://127.0.0.1:8000/health >/dev/null 2>&1; then
  echo "Backend already running on port 8000."
else
  source "$ROOT/.venv/bin/activate"
  nohup uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 >/tmp/cuad_backend.log 2>&1 &
  echo "Started backend (logs: /tmp/cuad_backend.log)"
fi

# In JupyterHub, localhost:5173 refers to the remote server from inside the
# container, not the user's browser. Start with the Hub proxy prefix so Vite
# assets and API requests work when opened through the browser.
if [[ -n "${JUPYTERHUB_SERVICE_PREFIX:-}" ]]; then
  FRONTEND_PORT=${CONTRACT_REVIEW_PORT:-5174}
  FRONTEND_BASE="${JUPYTERHUB_SERVICE_PREFIX%/}/proxy/${FRONTEND_PORT}/"
  FRONTEND_CHECK_URL="http://127.0.0.1:${FRONTEND_PORT}${FRONTEND_BASE}"
else
  FRONTEND_PORT=${CONTRACT_REVIEW_PORT:-5173}
  FRONTEND_BASE=${CONTRACT_REVIEW_BASE_PATH:-/}
  FRONTEND_CHECK_URL="http://127.0.0.1:${FRONTEND_PORT}/"
fi

if curl -sf "$FRONTEND_CHECK_URL" >/dev/null 2>&1; then
  echo "Frontend already running on port ${FRONTEND_PORT}."
else
  nohup env PORT="$FRONTEND_PORT" CONTRACT_REVIEW_BASE_PATH="$FRONTEND_BASE" \
    npm --prefix "$ROOT/frontend" run dev -- --host 0.0.0.0 --port "$FRONTEND_PORT" --strictPort \
    >/tmp/cuad_frontend.log 2>&1 &
  echo "Started frontend on port ${FRONTEND_PORT} (logs: /tmp/cuad_frontend.log)"
fi

if [[ -n "${JUPYTERHUB_SERVICE_PREFIX:-}" ]]; then
  echo "Open this path in the same JupyterHub browser: ${JUPYTERHUB_SERVICE_PREFIX%/}/proxy/${FRONTEND_PORT}/"
else
  echo "Open http://127.0.0.1:${FRONTEND_PORT}/ in the browser on the same machine."
fi
