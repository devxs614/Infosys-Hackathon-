#!/usr/bin/env bash
set -euo pipefail
PORT="${PORT:-8765}"
curl --fail --silent --show-error "http://127.0.0.1:${PORT}/health"
echo

