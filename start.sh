#!/bin/sh
set -eu

if [ ! -d "backend" ]; then
  echo "backend directory not found"
  exit 1
fi

cd backend

# Railway Shell runtime may start without build-layer site-packages, so install deps at launch.
python -m pip install --no-cache-dir -e .

exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
