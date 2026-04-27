#!/usr/bin/env bash
set -euo pipefail

URL="${1:-http://127.0.0.1:8088/}"
UNLOCK_FILE="${KIOSK_UNLOCK_FILE:-/etc/qrpass/kiosk.unlock}"

find_browser() {
  for c in /usr/bin/chromium /usr/bin/chromium-browser /usr/bin/google-chrome /snap/bin/chromium; do
    if [[ -x "$c" ]]; then
      echo "$c"
      return 0
    fi
  done
  return 1
}

BROWSER="$(find_browser || true)"
if [[ -z "${BROWSER}" ]]; then
  echo "No chromium/chrome found"
  exit 1
fi

COMMON_FLAGS=(
  --noerrdialogs
  --disable-infobars
  --no-first-run
  --disable-session-crashed-bubble
  --disable-restore-session-state
  --disable-pinch
  --overscroll-history-navigation=0
)

if [[ -f "${UNLOCK_FILE}" ]]; then
  # Админ-режим: можно свернуть/переключаться.
  exec "${BROWSER}" "${COMMON_FLAGS[@]}" "${URL}"
else
  # Жёсткий режим kiosk.
  exec "${BROWSER}" --kiosk "${COMMON_FLAGS[@]}" "${URL}"
fi
