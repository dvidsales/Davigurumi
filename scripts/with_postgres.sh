#!/usr/bin/env bash
set -euo pipefail
cd /workspace/Davigurumi
set -a
source .local/postgres.env
set +a
export POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=54329 POSTGRES_SSLMODE=disable
if [ -n "${DAVIGURUMI_TEST_DB:-}" ]; then export POSTGRES_DB="$DAVIGURUMI_TEST_DB"; fi
# TLS is disabled solely on this loopback-only development container.
exec /workspace/.venvs/davigurumi/bin/python "$@"
