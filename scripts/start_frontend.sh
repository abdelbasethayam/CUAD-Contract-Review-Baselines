#!/usr/bin/env bash
set -e
cd /home/jovyan/CUAD-Contract-Review-Baselines/frontend
echo "CUAD Contract Review - Frontend"
echo "URL: http://127.0.0.1:5173"
echo "Press Ctrl+C to stop."
exec npm run dev -- --host 0.0.0.0
