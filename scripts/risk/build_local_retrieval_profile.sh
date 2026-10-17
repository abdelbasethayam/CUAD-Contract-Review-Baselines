#!/usr/bin/env bash
# Rebuild the local retrieval profile and run the rule-first conformance checks.
# Stop the FastAPI backend first: embedded local Qdrant permits one process.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
PYTHON="$ROOT/.venv/bin/python"

if curl -fsS --max-time 2 http://127.0.0.1:8000/health >/dev/null 2>&1; then
  echo "ERROR: stop the backend before rebuilding local Qdrant indexes (port 8000 is healthy)." >&2
  echo "The embedded Qdrant storage folder is single-process." >&2
  exit 2
fi

export PYTHONPATH="$ROOT:$ROOT/backend:$ROOT/.venv/lib/python3.12/site-packages"
export PATH="$ROOT/.venv/bin:$PATH"

echo "[1/9] Build CUAD train-only hashing index"
"$PYTHON" scripts/risk/build_local_hashing_index.py --collection cuad_train_hashing

echo "[2/9] Build local legal-knowledge hashing index"
"$PYTHON" -m backend.app.core.legal_knowledge.ingest --collection legal_knowledge_hashing

echo "[3/9] Validate and hash both indexes"
"$PYTHON" scripts/risk/write_local_index_manifests.py

echo "[4/9] Validate the executable playbook rules"\n"$PYTHON" scripts/risk/validate_playbook_rules.py\n\necho "[5/9] Run train/test and index integrity checks"
"$PYTHON" scripts/risk/validate_evaluation_integrity.py

echo "[6/9] Validate playbook domains and regenerate the team export"
"$PYTHON" scripts/risk/normalize_playbook_domains.py
"$PYTHON" scripts/risk/export_team_pack.py

echo "[7/9] Validate representative legal guidance retrieval"
"$PYTHON" scripts/risk/validate_legal_knowledge.py

echo "[8/9] Evaluate held-out CUAD category retrieval with the local hashing baseline"
"$PYTHON" scripts/risk/evaluate_local_hashing_baseline.py

echo "[9/9] Rebuild the playbook-rule conformance report and run backend tests"
"$PYTHON" scripts/risk/report_phase2_experiment.py
PYTHONPATH="$ROOT:$ROOT/backend:$ROOT/.venv/lib/python3.12/site-packages" "$PYTHON" -m pytest -q backend/tests

echo "Local retrieval profile rebuilt. Start the application with: bash scripts/start_all.sh"
echo "After TXT and PDF upload smoke tests complete, stop the backend and run scripts/risk/run_release_checks.py to validate the full release artifacts."
