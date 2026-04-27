#!/usr/bin/env bash
set -euo pipefail

echo "[1/4] Reload units"
sudo systemctl daemon-reload

echo "[2/4] Enable edge service"
sudo systemctl enable --now qrpass-edge.service

echo "[3/4] Enable kiosk service"
sudo systemctl enable --now qrpass-edge-kiosk-chromium.service

echo "[4/4] Status"
systemctl --no-pager --full status qrpass-edge.service | sed -n '1,18p' || true
systemctl --no-pager --full status qrpass-edge-kiosk-chromium.service | sed -n '1,20p' || true
