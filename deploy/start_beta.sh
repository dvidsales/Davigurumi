#!/usr/bin/env bash
set -euo pipefail
python manage.py check --deploy --fail-level ERROR
python manage.py check_beta --strict
python manage.py migrate --noinput
exec gunicorn config.wsgi:application --bind "0.0.0.0:${PORT:-8000}" --workers 1 --threads 2 --timeout 120 --max-requests 500 --max-requests-jitter 50
