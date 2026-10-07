#!/usr/bin/env bash
set -euo pipefail
cd /workspace/Davigurumi
# The ignored file is generated locally; never print it or commit it.
if [ ! -f .local/postgres.env ]; then
  if [ -d .local/postgres ] || docker container inspect davigurumi-postgres > /dev/null 2>&1; then
    echo 'Há dados/container existentes sem o arquivo de credenciais. Recupere a configuração local; não regeneramos senha sobre dados existentes.' >&2
    exit 1
  fi
  /workspace/.venvs/davigurumi/bin/python -c 'from pathlib import Path; import secrets; p=Path(".local/postgres.env"); p.parent.mkdir(exist_ok=True); p.write_text("POSTGRES_DB=davigurumi\nPOSTGRES_USER=davigurumi\nPOSTGRES_PASSWORD="+secrets.token_urlsafe(32)+"\n"); p.chmod(0o600)'
fi
if docker container inspect davigurumi-postgres > /dev/null 2>&1; then
  docker start davigurumi-postgres > /dev/null
else
  docker run -d --name davigurumi-postgres -p 127.0.0.1:54329:5432 --env-file .local/postgres.env -v /workspace/Davigurumi/.local/postgres:/var/lib/postgresql/data postgres:17 > /dev/null
fi
for attempt in $(seq 1 30); do
  if docker exec davigurumi-postgres pg_isready -U davigurumi -d davigurumi > /dev/null; then
    exit 0
  fi
  sleep 1
done
echo 'PostgreSQL não iniciou em 30 segundos.' >&2
exit 1
