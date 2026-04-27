# QRPass Edge (Linux mini-PC)

Локальный сервис: SQLite-очередь нарушений, фоновая отправка на `qrpass_web` (`POST /api/violation`), автоочистка каталога снимков, минимальный UI на `127.0.0.1`.

**Не «оболочка» над `qrpass_client`:** на Linux-мини‑ПК обычно ставят **только этот пакет** — очередь и отправка живут здесь. **`qrpass_client`** — отдельный Windows-клиент (GUI/сборка); с edge он **пока не связан**. Детектор на мини‑ПК вызывает CLI ниже или ваш скрипт кладёт файл и пишет в ту же SQLite-очередь, пока крутится `python -m app.main`.

## Быстрый старт (разработка)

```bash
cd qrpass_edge
python -m venv .venv
.venv/Scripts/activate   # Windows
# source .venv/bin/activate  # Linux
pip install -r requirements.txt
copy .env.example .env   # задать SERVER_URL, API_TOKEN, пути
python -m app.main
```

Откройте http://127.0.0.1:8088/ — статистика очереди, ping сервера, тестовая постановка файла в очередь.
Настройка камер на объекте: http://127.0.0.1:8088/cameras
Журнал сработок с фильтрами: http://127.0.0.1:8088/events
Логи edge: http://127.0.0.1:8088/logs
Файлы нарушений: http://127.0.0.1:8088/files
На главной можно менять папку хранения файлов нарушений (сохраняется в локальной БД edge).

## CLI: поставить снимок в очередь (для детектора / cron)

Пока работает основной сервис (`app.main`), агент заберёт событие и отправит на сервер.

```bash
python -m app.enqueue_violation --file ./shot.jpg --camera "ФФО-1" --type "Нет каски"
```

Если файл во временной папке — скопировать в `STORAGE_ROOT`:

```bash
python -m app.enqueue_violation --file /tmp/x.jpg --camera "ФФО-1" --type "Тест" --copy-to-storage
```

## Heartbeat и preview-кадр (для живого дашборда)

Фоновый агент сам шлёт heartbeat в `/api/heartbeat` с интервалом
`HEARTBEAT_INTERVAL_SECONDS` (по умолчанию 10 сек), камера — `DEFAULT_CAMERA_NAME`.

Можно вызывать вручную/из детектора:

```bash
python -m app.edge_sync heartbeat --camera "ФФО-1"
python -m app.edge_sync frame --camera "ФФО-1" --file ./preview.jpg
```

## Встраивание в процесс детектора (рекомендуется)

Если детектор уже работает как Python-процесс, не обязательно вызывать CLI:
используйте адаптер напрямую.

```python
from pathlib import Path
from app.detector_adapter import EdgeDetectorAdapter

edge = EdgeDetectorAdapter(camera_name="ФФО-1")

# в основном цикле
edge.heartbeat_if_due()
edge.send_preview_frame(Path("./preview.jpg"), rule_summary="line-A")

# при нарушении
edge.enqueue_violation(Path("./violation.jpg"), "Нет униформы", copy_to_storage=True)
```

`enqueue_violation(...)` кладёт запись в локальную очередь; отправка на сайт происходит
асинхронно агентом `app.main` (или `qrpass-edge.service`).

## Локальная настройка камер (UI)

Страница `/cameras` поддерживает:
- добавление / редактирование / удаление камер;
- поля адреса, логина, пароля;
- выбор проверок списком `checks` (csv, например `color,perimeter,count_live,count_dead`);
- статус камеры `online/offline` по локальному heartbeat.

Редактирование выполняется через форму сверху: нажмите `Ред.` в строке камеры,
форма заполнится текущими данными.

## Переменные окружения

См. `.env.example`: `QUEUE_DB_PATH`, `STORAGE_ROOT`, `STORAGE_MAX_GB` (0 = не чистить), `SERVER_URL`, `API_TOKEN`, `SITE_NAME`, `EDGE_UI_HOST`, `EDGE_UI_PORT`, `AGENT_POLL_SECONDS`.

Для работы на очень медленном/нестабильном интернете можно включить локальный режим:
`UPSTREAM_ENABLED=false`. Тогда edge не отправляет heartbeat/stream/violations на сайт,
но локальный UI, preview и очередь продолжают работать.

Если нужно отправлять на сайт всё, кроме видеопотока:
- `UPSTREAM_ENABLED=true`
- `UPSTREAM_STREAM_ENABLED=false`

В этом режиме heartbeat и нарушения уходят на сервер, а `stream_frame` остаётся только локально (preview в edge UI).

На главной странице есть кнопки `Старт/Стоп/Рестарт сервиса` для systemd-сервиса детектора.
Имя сервиса задаётся через `CLIENT_SERVICE_NAME` (по умолчанию `qrpass-client.service`).

Если кнопка `Открыть папку` не срабатывает, проверьте GUI-сессию (`DISPLAY`) и наличие файлового менеджера
(`xdg-open`/`gio`/`nautilus`/`thunar` и т.д.). В ошибке в UI показывается точная причина.

Если иногда пропадает сеть/DNS, heartbeat может временно падать — это не критично
для очереди нарушений. Частоту одинаковых warning в логах регулирует
`HEARTBEAT_ERROR_LOG_COOLDOWN_SECONDS`.

`SERVER_URL` должен совпадать с базовым URL веб-приложения (включая root path, если он задан на хостинге).

## systemd

Примеры юнитов: `systemd/qrpass-edge.service` и `systemd/qrpass-edge-kiosk-chromium.service`.

1. Скопируйте проект в `/opt/qrpass_edge`, создайте пользователя `qrpass`, виртуальное окружение и `/etc/qrpass/edge.env` по образцу `.env.example`.
2. `sudo systemctl enable --now qrpass-edge.service`
3. Для киоска: автологин в графическую сессию, затем `enable --now qrpass-edge-kiosk-chromium.service` (порт в URL должен совпадать с `EDGE_UI_PORT`).

Chromium открывает только локальный UI; доступ в интернет для отправки очереди — по политике сети объекта.

### Быстрая установка/обновление на мини-ПК

Из каталога `/opt/qrpass_edge`:

```bash
sudo bash scripts/install_or_update_service.sh
```

После этого заполните `/etc/qrpass/edge.env` (минимум `SERVER_URL`, `API_TOKEN`),
затем перезапустите:

```bash
sudo systemctl restart qrpass-edge.service
```

### Smoke-check после выката

```bash
bash scripts/smoke_test_edge.sh
```

Проверка должна показать:
- `/health` с `ok=true`
- `/api/queue/stats` без ошибок
- `/api/ping` с `ok=true` (или понятной ошибкой сети/токена)

### Проверка kiosk + автозапуска

```bash
bash scripts/enable_kiosk.sh
bash scripts/check_kiosk_autostart.sh
```

Если `qrpass-edge-kiosk-chromium.service` не поднимается:
- проверьте, что есть GUI-сеанс и автологин;
- проверьте `journalctl -u qrpass-edge-kiosk-chromium.service -n 50 --no-pager`;
- убедитесь, что установлен Chromium/Chrome (unit ищет несколько путей автоматически).

### Жёсткий kiosk + админский выход

По умолчанию kiosk стартует в жёстком режиме.
Чтобы временно включить админский режим (можно свернуть/переключиться):

```bash
sudo touch /etc/qrpass/kiosk.unlock
sudo systemctl restart qrpass-edge-kiosk-chromium.service
```

Вернуть жёсткий режим:

```bash
sudo rm -f /etc/qrpass/kiosk.unlock
sudo systemctl restart qrpass-edge-kiosk-chromium.service
```

Примечание: в `journal tail` могут быть старые красные ошибки от прошлых запусков.
Проверяйте актуальный статус сервиса отдельной командой `systemctl is-active ...`.
