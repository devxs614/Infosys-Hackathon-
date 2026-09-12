#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if [ -f .venv/bin/activate ]; then . .venv/bin/activate; fi
uvicorn edge_server.main:app --host "${HOST:-0.0.0.0}" --port "${PORT:-8765}" &
SERVER_PID=$!
trap 'kill "$SERVER_PID" 2>/dev/null || true' EXIT
sleep 2
curl -fsS -X POST "http://127.0.0.1:${PORT:-8765}/demo/start"
wait "$SERVER_PID"

