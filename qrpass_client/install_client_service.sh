#!/usr/bin/env bash
set -euo pipefail

# Скрипт для создания systemd-сервиса для qrpass_client
# Выполнять на мини-ПК: sudo ./install_client_service.sh

if [[ $EUID -ne 0 ]]; then
   echo "Этот скрипт нужно запускать с sudo" 
   exit 1
fi

CLIENT_DIR="/home/smolpole1/camera detect/new2/qrpass_client"
SERVICE_FILE="/etc/systemd/system/qrpass-client.service"

echo "=== Установка сервиса qrpass-client ==="

# Проверяем, существует ли папка
if [[ ! -d "$CLIENT_DIR" ]]; then
    echo "Внимание: Папка $CLIENT_DIR не найдена."
    echo "Убедитесь, что qrpass_client находится в $CLIENT_DIR"
    echo "Или измените путь в этом скрипте."
    # Мы не прерываем скрипт, сервис просто будет падать, пока папку не создадут
fi

cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=QRPass Client (Detector)
After=network.target qrpass-edge.service
Wants=qrpass-edge.service

[Service]
Type=simple
User=smolpole1
Group=smolpole1
WorkingDirectory=$CLIENT_DIR

# Загружаем переменные окружения (включая EDGE_BRIDGE_URL)
EnvironmentFile=-$CLIENT_DIR/.env

# Если запускали через системный python или VS Code:
ExecStart=/usr/bin/python3 main.py

Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

echo "Перезагрузка systemd..."
systemctl daemon-reload

echo "Включение автозапуска..."
systemctl enable qrpass-client.service

echo "Запуск сервиса..."
systemctl restart qrpass-client.service

echo "=== Готово! ==="
echo "Статус можно проверить командой: sudo systemctl status qrpass-client.service"
echo "Логи: sudo journalctl -u qrpass-client.service -f"