#!/usr/bin/env bash
set -euo pipefail

echo "== QRPass Edge / Kiosk Autostart Check =="
echo

echo "[1/8] Service files"
systemctl cat qrpass-edge.service >/dev/null
systemctl cat qrpass-edge-kiosk-chromium.service >/dev/null
echo "OK: unit files доступны"

echo "[2/8] Edge service enabled/active"
echo -n "enabled: "; systemctl is-enabled qrpass-edge.service || true
echo -n "active : "; systemctl is-active qrpass-edge.service || true

echo "[3/8] Kiosk service enabled/active"
echo -n "enabled: "; systemctl is-enabled qrpass-edge-kiosk-chromium.service || true
echo -n "active : "; systemctl is-active qrpass-edge-kiosk-chromium.service || true

echo "[4/8] Browser binary"
BROWSER=""
for c in /usr/bin/chromium /usr/bin/chromium-browser /usr/bin/google-chrome /snap/bin/chromium; do
  if [[ -x "$c" ]]; then BROWSER="$c"; break; fi
done
if [[ -z "$BROWSER" ]]; then
  echo "WARN: Chromium/Chrome не найден."
else
  echo "OK: найден браузер -> $BROWSER"
fi

echo "[5/8] GUI session env"
echo "DISPLAY=${DISPLAY:-<empty>}"
if [[ -z "${DISPLAY:-}" ]]; then
  echo "WARN: DISPLAY не задан в текущей сессии. Для kiosk нужен GUI/autologin."
fi

echo "[6/8] Edge HTTP health"
curl -fsS "http://127.0.0.1:8088/health" || echo "WARN: /health недоступен"
echo

echo "[7/8] Journal tail (edge)"
journalctl -u qrpass-edge.service -n 12 --no-pager || true

echo "[8/8] Journal tail (kiosk)"
journalctl -u qrpass-edge-kiosk-chromium.service -n 20 --no-pager || true

echo
echo "Done."
