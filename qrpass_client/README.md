# QRPass Client (локальный ПК / объект)

Клиент захватывает видео, обрабатывает YOLOv8 и отправляет на сервер **qrpass_web**:

- Heartbeat (`POST /api/heartbeat`) — по умолчанию каждые 5 с
- Кадр с разметкой (`POST /api/stream_frame`) — по умолчанию каждые 0.5 с
- Нарушение (`POST /api/violation`) — при детекции с кулдауном

Заголовок `X-API-Token` должен совпадать с `CLIENT_API_TOKEN` на хостинге.

Для Linux mini-PC по текущему ТЗ можно оставить детекцию в `qrpass_client`, а транспорт
вести через локальный `qrpass_edge`: задайте `EDGE_BRIDGE_URL=http://127.0.0.1:8088`.
Тогда `heartbeat/stream/violation` идут сначала в edge (локально), а edge отправляет на сайт
и буферизует оффлайн.

**Полная пошаговая установка на объект (Linux, venv, `.env`, `best.pt`, проверки):** см. [DEPLOY_OBJECT.md](DEPLOY_OBJECT.md).

### Режим как на старом объекте (`mdb.py`, `users.db`)

Если камеры и RTSP уже заведены в SQLite через ваш `mdb.py` / Telegram-бот (`jdb.py`):

1. **Не запускайте одновременно** старый `main.py` (YOLO+Telegram) и этот клиент на **те же** RTSP — будет двойной захват потока.
2. В `.env` включите `USE_MDB_CAMERAS=true`, задайте `SERVER_URL` и `API_TOKEN` как выше.
3. Запускайте клиент **из каталога**, где лежат `mdb.py` и `users.db`, **или** укажите `MDB_PARENT_DIR` — туда же выполнится переход по `chdir`, чтобы пути к `users.db` в `mdb.py` совпали.
4. Имена камер на сайте совпадают с полем `name` в таблице `Cameras` (как в `mdb.get_cameras()`).
5. Нарушения: по умолчанию — классы из `VIOLATION_CLASSES`; иначе включите `USE_TRAINED_MODEL` или `USE_COLOR_VIOLATIONS` (см. ниже и [DEPLOY_OBJECT.md](DEPLOY_OBJECT.md)).

Файл `mdb_runtime.py` подгружает `mdb.py` из текущей папки или из `MDB_MODULE_FILE`.

### Обученная модель (`old/main.py`, папка `old/`)

Включите `USE_TRAINED_MODEL=true`, путь к весам **`YOLO_MODEL_PATH=best.pt`** (не стандартный `yolov8n.pt` с COCO — иначе в нарушениях появятся `umbrella`, `sink` и т.д.). Порог `TRAINED_CONF_THRESHOLD`. Логика в `trained_model_rules.py`: политика зон `check_access_rule` по `Rules` для `POLICY_COLOR_IDS` (2, 6, 7), как в комментариях `old/main.py` (зона без красного → только person-класс, зона с формой → только red uniform). Сравнение классов **без учёта регистра** (`person` / `Person`). К учёту нарушений допускаются только классы из `POLICY_TRACKED_CLASSES` (по умолчанию Person, Red uniform, Barrel) — прочие детекты игнорируются.

Если одновременно включить `USE_COLOR_VIOLATIONS`, приоритет у **обученной модели**.

### Нарушения по HSV и сегментации (другой legacy-режим)

`USE_COLOR_VIOLATIONS=true`, модель сегментации, логика в `color_rules.py`.

- **Несколько камер** (`USE_MDB_CAMERAS=true`): `id` камеры из БД.
- **Одна камера**: `CAMERA_ID`, `MDB_PARENT_DIR` при необходимости.

Без этих режимов используется детекция по `VIOLATION_CLASSES` и произвольная модель.

## Установка

```bash
pip install -r requirements.txt
```

## Настройка `.env`

1. Скопируйте `.env.example` в `.env`.
2. Заполните переменные:

| Переменная | Описание |
|------------|----------|
| `SERVER_URL` | Базовый URL сайта **qrpass_web**. Локально: `http://127.0.0.1:8000`. На объекте: `https://ваш-домен.ru` без слэша в конце (в коде выполняется `rstrip("/")`). |
| `API_TOKEN` | Тот же секрет, что **`CLIENT_API_TOKEN`** в `.env` сервера. |
| `USE_MDB_CAMERAS` | `true` — брать список камер из `mdb.get_cameras()` / `users.db`; иначе одна камера из `CAMERA_NAME` + `CAMERA_SOURCE`. |
| `MDB_PARENT_DIR` | Каталог со старыми `mdb.py` и `users.db`, если клиент запускается не из него (там же выполняется рабочий каталог процесса). |
| `MDB_MODULE_FILE` | Полный путь к `mdb.py`, если файл не называется стандартно или лежит вне текущей папки. |
| `CAMERA_NAME` | Однокамерный режим: имя на дашборде. В режиме mdb имена берутся из таблицы `Cameras`. |
| `CAMERA_SOURCE` | Однокамерный режим: индекс веб-камеры (`0`) или RTSP-URL. |
| `YOLO_MODEL_PATH` | Путь к весам модели. |
| `VIOLATION_CLASSES` | Классы YOLO, при которых считать нарушение (через запятую). |
| `VIOLATION_COOLDOWN_SECONDS` | Минимальный интервал между отправками нарушений. |
| `STREAM_INTERVAL_SECONDS` / `HEARTBEAT_INTERVAL_SECONDS` | Интервалы отправки кадров и heartbeat. |

Telegram-бот (`jdb.py`) можно оставить для управления камерами в SQLite; веб-клиент только читает `users.db` и шлёт кадры на сайт. Не запускайте параллельно старый `main.py` с теми же RTSP.

## Запуск

```bash
python main.py
```

## Сборка Windows `.exe` (без исходников рядом)

> Важно: упаковка в exe скрывает исходники от обычного пользователя, но не является полной защитой от реверса.

1. Откройте PowerShell в `qrpass_client`.
2. Соберите клиент:

```powershell
.\build_exe.ps1 -EntryPoint main.py -ExeName QRPassClient
```

Для GUI-лаунчера:

```powershell
.\build_exe.ps1 -EntryPoint gui.py -ExeName QRPassLauncher -Windowed
```

Результат: папка `dist\QRPassClient\` (или `dist\QRPassLauncher\`) + `.env.example`.

Для полного релиз-пакета под Windows без Python:

```powershell
.\package_windows_release.ps1 -ExeName QRPassClient
```

См. также: [DEPLOY_WINDOWS_NO_PYTHON.md](DEPLOY_WINDOWS_NO_PYTHON.md).

## Импорт камер из Excel в SQLite (`Cameras`)

Если есть файл вроде `IP_Cams_FFO4.xlsx`, можно сгенерировать SQL:

```bash
pip install openpyxl
python scripts/xlsx_to_cameras_sql.py --xlsx "C:\path\IP_Cams_FFO4.xlsx" --out "sql\update_cameras_from_xlsx.sql"
```

Скрипт читает по умолчанию:
- имя камеры из колонки 8
- RTSP URL из колонки 9
- данные начиная со строки 2

Далее выполните полученный SQL в `users.db`.

Графический лаунчер (правка полей, старт/стоп, лог):

```bash
python gui.py
```

На Linux при отсутствии окна: `sudo apt install python3-tk`.

### Visual Studio Code

1. **File → Open Folder** — откройте каталог **`qrpass_client`** целиком (тогда подхватится `.vscode/launch.json`).
2. Установите расширение **Python** (Microsoft). Для отладки: `pip install debugpy` в том же venv, что и клиент.
3. **Run and Debug (F5)** — конфигурации «Клиент: main.py» и «Клиент: gui.py»; переменные окружения подтягиваются из `.env` в корне `qrpass_client` (`envFile` в `launch.json`).

Если у вас в другом проекте (например `new2/`) лежат **PyArmor**-сборки в `dist/` и старый `main.py` — это **отдельный** процесс. Клиент QRPass удобно держать копией папки `qrpass_client` рядом или в подкаталоге; для `USE_MDB_CAMERAS` задайте `MDB_PARENT_DIR` на каталог с **`mdb.py` и `users.db`**. Если `mdb.py` только в обфусцированном виде, нужна та же среда PyArmor; проще для веб-клиента оставить рядом несжатый `mdb.py`, который только читает ту же БД.

В логах не должно быть стабильных `401` (неверный токен) или ошибок SSL (проверьте `https://` и сертификат домена). **Пароли в RTSP-URL** не светите в скриншотах и чатах — при утечке смените пароль камеры и обновите URL в БД.

## Проверка связи с сайтом

1. На сервере в `.env` заданы `CLIENT_API_TOKEN` и (для продакшена) `SEED_DEMO_DATA=false`.
2. В браузере под админом откройте «Статус системы» — после запуска клиента камера с именем `CAMERA_NAME` должна стать «Онлайн» (отклик &lt; 15 с).
3. Страница «Онлайн-камеры» — поток `/stream/<CAMERA_NAME>` показывает кадры.
4. При срабатывании детекции — запись на главной и при настроенной почте письмо.
