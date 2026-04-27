#!/usr/bin/env bash
set -euo pipefail

# Smoke-проверка edge на мини-ПК.
# Запуск:
#   bash scripts/smoke_test_edge.sh

UI_URL="${1:-http://127.0.0.1:8088}"

echo "[1/5] health"
curl -fsS "${UI_URL}/health" >/tmp/edge_health.json
cat /tmp/edge_health.json
echo

echo "[2/5] queue stats"
curl -fsS "${UI_URL}/api/queue/stats" >/tmp/edge_stats.json
cat /tmp/edge_stats.json
echo

echo "[3/5] ping server via edge"
curl -fsS -X POST "${UI_URL}/api/ping" >/tmp/edge_ping.json
cat /tmp/edge_ping.json
echo

echo "[4/5] systemd status (if available)"
if command -v systemctl >/dev/null 2>&1; then
  systemctl is-active qrpass-edge.service || true
fi

echo "[5/5] done"
echo "Smoke completed for ${UI_URL}"
