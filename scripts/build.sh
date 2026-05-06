#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=== Soaring Heights KMS Build ==="

cd "$PROJECT_ROOT"

echo "[1/4] Building frontend..."
cd frontend
npm install
npm run build
cd "$PROJECT_ROOT"

echo "[2/4] Building Docker images..."
docker compose build

echo "[3/4] Starting containers..."
docker compose up -d

echo "[4/4] Reloading Nginx..."
nginx -s reload

echo "=== Build complete ==="
echo "Frontend: http://kennel.soaringheights.local"
echo "API docs: http://kennel.soaringheights.local/docs"
