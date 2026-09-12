#!/usr/bin/env bash
set -euo pipefail
if [ -f .env ]; then
  set -a
  . ./.env
  set +a
fi
PORT="${PORT:-8000}"
curl --fail --silent --show-error "http://127.0.0.1:${PORT}/health"
echo
