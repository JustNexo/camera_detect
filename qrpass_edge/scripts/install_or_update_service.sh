#!/usr/bin/env bash
set -euo pipefail

# Установка/обновление qrpass_edge как systemd-сервиса.
# Запуск:
#   sudo bash scripts/install_or_update_service.sh

APP_DIR="/opt/qrpass_edge"
APP_USER="qrpass"
APP_GROUP="qrpass"
ENV_DIR="/etc/qrpass"
ENV_FILE="${ENV_DIR}/edge.env"
UNIT_DIR="/etc/systemd/system"

echo "[1/7] Проверка прав"
if [[ "${EUID}" -ne 0 ]]; then
  echo "Нужен root (запустите через sudo)." >&2
  exit 1
fi

echo "[2/7] Создание пользователя/группы"
if ! id -u "${APP_USER}" >/dev/null 2>&1; then
  useradd --system --create-home --shell /usr/sbin/nologin "${APP_USER}"
fi

echo "[3/7] Подготовка каталогов"
mkdir -p "${APP_DIR}" "${ENV_DIR}" /var/lib/qrpass
chown -R "${APP_USER}:${APP_GROUP}" "${APP_DIR}" /var/lib/qrpass

echo "[4/7] Копирование unit-файлов"
install -m 0644 "${APP_DIR}/systemd/qrpass-edge.service" "${UNIT_DIR}/qrpass-edge.service"
install -m 0644 "${APP_DIR}/systemd/qrpass-edge-kiosk-chromium.service" "${UNIT_DIR}/qrpass-edge-kiosk-chromium.service"

echo "[5/7] Проверка edge.env"
if [[ ! -f "${ENV_FILE}" ]]; then
  if [[ -f "${APP_DIR}/.env.example" ]]; then
    cp "${APP_DIR}/.env.example" "${ENV_FILE}"
    echo "Создан ${ENV_FILE}. Заполните SERVER_URL/API_TOKEN и пути."
  else
    cat > "${ENV_FILE}" <<'EOF'
QUEUE_DB_PATH=/var/lib/qrpass/edge_queue.db
STORAGE_ROOT=/var/lib/qrpass/violations
STORAGE_MAX_GB=150
SERVER_URL=https://example.com
API_TOKEN=change_me_api_token
SITE_NAME=
EDGE_UI_HOST=127.0.0.1
EDGE_UI_PORT=8088
AGENT_POLL_SECONDS=5
HEARTBEAT_INTERVAL_SECONDS=10
HEARTBEAT_ERROR_LOG_COOLDOWN_SECONDS=60
DEFAULT_CAMERA_NAME=EDGE-CAM-1
EOF
    echo "Создан ${ENV_FILE}. Заполните SERVER_URL/API_TOKEN."
  fi
fi

echo "[6/7] Виртуальное окружение"
if [[ ! -x "${APP_DIR}/.venv/bin/python" ]]; then
  sudo -u "${APP_USER}" python3 -m venv "${APP_DIR}/.venv"
fi
sudo -u "${APP_USER}" "${APP_DIR}/.venv/bin/pip" install -r "${APP_DIR}/requirements.txt"

echo "[7/7] Перезапуск systemd"
systemctl daemon-reload
systemctl enable --now qrpass-edge.service
systemctl restart qrpass-edge.service
systemctl --no-pager --full status qrpass-edge.service | sed -n '1,20p'

echo "Готово. Проверка UI: http://127.0.0.1:8088/"
