#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_LOG="${ROOT}/.local-backend.log"
FRONTEND_DIR="${ROOT}/frontend"

if [[ ! -d "${ROOT}/backend" || ! -d "${FRONTEND_DIR}" ]]; then
  echo "Run this script from a complete repository checkout." >&2
  exit 1
fi

if [[ -z "${COHERE_API_KEY:-}" ]]; then
  echo "COHERE_API_KEY is required for clause embeddings unless your configured pipeline replaces Cohere." >&2
  echo "Export it before running, for example: export COHERE_API_KEY=..." >&2
  exit 1
fi

export CORS_ORIGINS="${CORS_ORIGINS:-http://localhost:5173}"
export OLLAMA_URL="${OLLAMA_URL:-http://localhost:11434}"
export QDRANT_URL="${QDRANT_URL:-}"
export OPENROUTER_API_KEY="${OPENROUTER_API_KEY:-}"

if [[ -n "${QDRANT_URL}" ]]; then
  echo "Using remote Qdrant: ${QDRANT_URL}"
else
  echo "Using local Qdrant path: ${QDRANT_PATH:-data/qdrant_local}"
fi
echo "Using Ollama: ${OLLAMA_URL}"
echo "Sample contract: ${ROOT}/examples/phase2_demo_contract.txt"

cleanup() {
  if [[ -n "${BACKEND_PID:-}" ]] && kill -0 "${BACKEND_PID}" 2>/dev/null; then
    kill "${BACKEND_PID}" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

cd "${ROOT}"
PYTHONPATH="${ROOT}:${ROOT}/backend" python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000 >"${BACKEND_LOG}" 2>&1 &
BACKEND_PID=$!

for _ in {1..30}; do
  if curl -fsS http://127.0.0.1:8000/health >/dev/null; then
    break
  fi
  sleep 1
done
if ! curl -fsS http://127.0.0.1:8000/health >/dev/null; then
  echo "Backend did not start. Log: ${BACKEND_LOG}" >&2
  tail -80 "${BACKEND_LOG}" >&2 || true
  exit 1
fi

cd "${FRONTEND_DIR}"
if [[ ! -d node_modules ]]; then
  npm ci
fi
echo
echo "Open http://localhost:5173"
echo "Upload ${ROOT}/examples/phase2_demo_contract.txt"
echo "After Phase 2 completes, ask the chatbot: What are the highest-priority review items?"
echo
echo "Backend log: ${BACKEND_LOG}"
npm run dev -- --host 127.0.0.1
