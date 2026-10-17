#!/usr/bin/env bash
set -e
cd /home/jovyan/CUAD-Contract-Review-Baselines
source .venv/bin/activate
echo "CUAD Contract Review - Backend"
echo "URL: http://127.0.0.1:8000"
echo "Press Ctrl+C to stop."
exec uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
