# QRPass Demo

Проект разделен на две части:

- `qrpass_web` — веб-сервер для хостинга (FastAPI + Jinja2 + SQLite)
- `qrpass_client` — локальный edge-клиент (YOLOv8 + отправка heartbeat/потоков/нарушений)

Сначала поднимите `qrpass_web`, затем запустите `qrpass_client`.
