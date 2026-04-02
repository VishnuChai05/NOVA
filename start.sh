#!/bin/sh
set -eu

if [ ! -d "backend" ]; then
  echo "backend directory not found"
  exit 1
fi

cd backend

exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
