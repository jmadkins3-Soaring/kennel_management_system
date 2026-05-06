#!/usr/bin/env bash
# restart.sh — Rebuild and restart KMS containers.
# Requires sudo. Stops AppArmor, kills container PIDs, removes containers,
# brings them back up, then restarts AppArmor.
#
# Usage:
#   sudo ./restart.sh            # restart both backend and frontend
#   sudo ./restart.sh backend    # backend only
#   sudo ./restart.sh frontend   # frontend only
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

if [[ $EUID -ne 0 ]]; then
  echo "Run with sudo: sudo ./restart.sh [backend|frontend]"
  exit 1
fi

SERVICES=("${@:-backend frontend}")
if [[ $# -eq 0 ]]; then
  SERVICES=(backend frontend)
else
  SERVICES=("$@")
fi

echo "=== KMS Restart: ${SERVICES[*]} ==="

echo "[1] Building images (--no-cache)..."
docker compose build --no-cache "${SERVICES[@]}"

echo "[2] Stopping AppArmor..."
systemctl stop apparmor

echo "[3] Killing container PIDs..."
for svc in "${SERVICES[@]}"; do
  cids=$(docker ps -q --filter "name=${svc}" 2>/dev/null || true)
  if [[ -n "$cids" ]]; then
    for cid in $cids; do
      pid=$(docker inspect --format '{{.State.Pid}}' "$cid" 2>/dev/null || true)
      if [[ -n "$pid" && "$pid" != "0" ]]; then
        echo "  killing $svc PID $pid"
        kill -9 "$pid" 2>/dev/null || true
      fi
    done
  else
    echo "  $svc: no running containers found"
  fi
done

echo "[4] Removing containers..."
for svc in "${SERVICES[@]}"; do
  cids=$(docker ps -aq --filter "name=${svc}" 2>/dev/null || true)
  if [[ -n "$cids" ]]; then
    docker rm -f $cids
  else
    echo "  $svc: nothing to remove"
  fi
done

echo "[5] Starting containers..."
docker compose up -d "${SERVICES[@]}"

echo "[6] Restarting AppArmor..."
systemctl start apparmor

echo ""
echo "Waiting for backend health..."
for i in $(seq 1 15); do
  if curl -sf http://127.0.0.1:9101/api/health >/dev/null 2>&1; then
    echo "  Backend OK"
    break
  fi
  if [[ "$i" -eq 15 ]]; then
    echo "  Backend did not respond after 30s — check: docker compose logs backend"
    exit 1
  fi
  sleep 2
done

echo ""
docker compose ps
echo ""
echo "=== Restart complete ==="
