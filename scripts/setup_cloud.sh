#!/usr/bin/env bash
set -euo pipefail
cd /workspace/Davigurumi
if [ ! -f requirements.txt ] || [ ! -f manage.py ]; then
  echo 'Este checkout ainda não contém a aplicação. Selecione a branch de implementação ou incorpore o PR antes do setup.' >&2
  exit 1
fi
if [ ! -x /workspace/.venvs/davigurumi/bin/python ]; then
  python3 -m venv /workspace/.venvs/davigurumi
fi
export PIP_CACHE_DIR=/workspace/.cache/pip
/workspace/.venvs/davigurumi/bin/python -m pip install -r requirements.txt
bash scripts/dev_postgres.sh
bash scripts/with_postgres.sh manage.py migrate --noinput
bash scripts/with_postgres.sh manage.py check
bash scripts/with_postgres.sh manage.py reconcile_stock
