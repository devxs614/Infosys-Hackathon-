#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if [ -f .env ]; then
  set -a
  . ./.env
  set +a
fi
if [ -f .venv/bin/activate ]; then . .venv/bin/activate; fi
exec uvicorn edge_server.main:app --host "${HOST:-0.0.0.0}" --port "${PORT:-8000}"
