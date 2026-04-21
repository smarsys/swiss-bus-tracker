#!/usr/bin/env bash
set -e
pip install -r requirements.txt
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers "${WORKERS:-2}" --proxy-headers --forwarded-allow-ips="*"
