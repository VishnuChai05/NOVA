#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

ENV_FILE="${1:-.env.production}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1/api/health}"
MAX_ATTEMPTS="${MAX_ATTEMPTS:-30}"
SLEEP_SECONDS="${SLEEP_SECONDS:-2}"

if ! command -v docker >/dev/null 2>&1; then
  echo "[ERROR] docker is not installed or not in PATH"
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "[ERROR] docker compose plugin is not available"
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "[ERROR] Env file not found: $ENV_FILE"
  echo "Create it from .env.production.example first."
  exit 1
fi

echo "[INFO] Using env file: $ENV_FILE"
echo "[INFO] Building and starting services..."
docker compose --env-file "$ENV_FILE" up -d --build

echo "[INFO] Waiting for API health: $HEALTH_URL"
for ((i=1; i<=MAX_ATTEMPTS; i++)); do
  if curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
    echo "[OK] Deployment successful. API is healthy."
    docker compose ps
    exit 0
  fi
  sleep "$SLEEP_SECONDS"
done

echo "[ERROR] API health check failed after $MAX_ATTEMPTS attempts"
echo "[INFO] Recent backend logs:"
docker compose logs --tail=80 backend || true
exit 1
