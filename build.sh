#!/usr/bin/env bash
# build.sh — Full build and deploy: Docker build → up → Nginx reload → health check.
# Usage: ./build.sh
#
# Note: the frontend Dockerfile runs its own npm ci && npm run build inside the
# container (multi-stage build), so no host-side npm step is required here.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== Soaring Heights KMS Build ==="

cd "$PROJECT_ROOT"

echo "[1/3] Building Docker images..."
docker compose build

echo "[2/3] Starting containers..."
docker compose up -d

echo "[3/3] Reloading Nginx..."
if command -v nginx &>/dev/null; then
  if sudo -n nginx -s reload 2>/dev/null; then
    echo "  Nginx reloaded."
  else
    echo "  NOTE: Nginx reload requires sudo — run manually: sudo nginx -s reload"
  fi
else
  echo "  Nginx not found — skipping."
fi

# Wait for backend to be ready before declaring success.
echo ""
echo "Waiting for backend health..."
for i in $(seq 1 15); do
  if curl -sf http://127.0.0.1:9101/api/health >/dev/null 2>&1; then
    echo "  http://127.0.0.1:9101/api/health → OK"
    break
  fi
  if [ "$i" -eq 15 ]; then
    echo "  Backend did not respond after 30s."
    echo "  Check logs: docker compose logs backend"
    exit 1
  fi
  sleep 2
done

echo ""
echo "=== Build complete ==="
echo "Frontend : http://kennel.soaringheights.local"
echo "API docs : http://kennel.soaringheights.local/docs"
