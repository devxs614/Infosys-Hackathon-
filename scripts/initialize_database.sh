#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if [ ! -f .env ]; then
  echo "Missing .env. Copy the deployment-specific ignored .env file to this Raspberry Pi first." >&2
  exit 1
fi
set -a
. ./.env
set +a
: "${TIGER_DB_URL:?TIGER_DB_URL must be set in .env}"
command -v psql >/dev/null || { echo "psql is required: sudo apt install postgresql-client" >&2; exit 1; }
psql "$TIGER_DB_URL" -v ON_ERROR_STOP=1 -f database/schema.sql
echo "Telemetry schema is ready."
