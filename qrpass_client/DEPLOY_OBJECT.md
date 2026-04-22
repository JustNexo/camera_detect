# Развёртывание QRPass Client на объекте (Linux)

Пошаговая инструкция для машины, где уже лежит новая версия клиента и нужно запустить связку с сайтом **qrpass_web** и вашей обученной моделью (`old/main.py` → `USE_TRAINED_MODEL`).

---

## 1. Что должно быть на сервере сайта

На хостинге (Sprinthost и т.п.) уже настроены:

- Рабочий **HTTPS**-URL сайта, например `https://ваш-домен.ru` (без лишнего `https://http://`).
- В `.env` сайта заданы **`CLIENT_API_TOKEN`** и при необходимости **`ROOT_PATH`**, **`DATABASE_URL`**.

Вам нужны **точные значения**:

- базовый URL сайта (как в адресной строке, без `/` в конце);
- строка **`CLIENT_API_TOKEN`** — тот же секрет пропишете в клиенте как **`API_TOKEN`**.

---

## 2. Что положить на объект (ПК / NVR рядом с камерами)

Скопируйте на объект **каталог `qrpass_client`** целиком (или архивом), чтобы на диске было, например:

```text
/home/ВАШ_ПОЛЬЗОВАТЕЛЬ/camera_detect/new2/qrpass_client/
  main.py
  trained_model_rules.py
  color_rules.py      # можно не трогать, если не USE_COLOR_VIOLATIONS
  mdb_runtime.py
  gui.py
  requirements.txt
  .vscode/            # по желанию
```

Дополнительно **обязательно для вашей логики**:

| Файл | Назначение |
|------|------------|
| **`best.pt`** | Веса обученной YOLO (из папки `old/`). Положите **внутрь `qrpass_client`** или укажите **абсолютный путь** в `YOLO_MODEL_PATH`. |
| **`users.db`** | SQLite с таблицами `Cameras`, `Colors`, `Rules` (как у вас в проекте). Обычно лежит **в родительской папке** вместе с `mdb.py`, например `.../new2/users.db`. |

Если используете **несколько камер из БД** (`USE_MDB_CAMERAS=true`), рядом с `users.db` должен быть **`mdb.py`** (ваш старый модуль с `get_cameras()`).

### PyArmor (обфусцированный `mdb.py` в `dist/`)

Если `mdb.py` защищён PyArmor, рядом нужен каталог **`pyarmor_runtime_000000`** (часто он лежит в **корне проекта** `NEW2/`, а сам `mdb.py` — в `NEW2/dist/mdb.py`).

В `.env` укажите **полный путь** к обфусцированному файлу и при необходимости каталог рантайма:

```env
MDB_MODULE_FILE=/home/ВАШ/NEW2/dist/mdb.py
MDB_PARENT_DIR=/home/ВАШ/NEW2
PYARMOR_RUNTIME_DIR=/home/ВАШ/NEW2
```

`mdb_runtime.py` сам добавляет в `sys.path` папку с `mdb.py`, её родителя и `PYARMOR_RUNTIME_DIR`, чтобы импорт `pyarmor_runtime_000000` проходил без `ModuleNotFoundError`.

Если рантайм лежит **в той же папке**, что и `mdb.py` (например `dist/pyarmor_runtime_000000`), достаточно `MDB_MODULE_FILE`; `PYARMOR_RUNTIME_DIR` можно не задавать.

---

## 3. Python и виртуальное окружение

На объекте (терминал SSH или консоль на месте):

```bash
cd /home/ВАШ_ПОЛЬЗОВАТЕЛЬ/camera_detect/new2/qrpass_client
python3 --version   # желательно 3.10 или 3.11
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip wheel setuptools
pip install --prefer-binary -r requirements.txt
```

Если при установке падает **`greenlet`** — см. `README.md` (`--only-binary greenlet`, Python 3.10/3.11).

---

## 4. Файл `.env` в каталоге `qrpass_client`

Скопируйте `.env.example` → `.env` и заполните.

### Минимум для связи с сайтом

```env
SERVER_URL=https://ваш-домен.ru
API_TOKEN=тот_же_что_CLIENT_API_TOKEN_на_сервере
```

### Режим обученной модели + правила из `users.db` (как `old/main.py`)

```env
USE_TRAINED_MODEL=true
YOLO_MODEL_PATH=best.pt
TRAINED_CONF_THRESHOLD=0.5

POLICY_COLOR_IDS=2,6,7
POLICY_CLASS_PERSON=Person
POLICY_CLASS_UNIFORM=Red uniform
```

И **рабочий каталог для SQLite**: клиент при старте может сделать `chdir` в папку, где лежит **`users.db`**, если указать:

```env
MDB_PARENT_DIR=/home/ВАШ_ПОЛЬЗОВАТЕЛЬ/camera_detect/new2
```

(путь **без** завершающего `/`, подставьте свой; это каталог, где у вас `users.db` и при необходимости `mdb.py`.)

### Одна камера (без `USE_MDB_CAMERAS`)

В таблице `Cameras` найдите строку вашей камеры и её **`id`**:

```env
USE_MDB_CAMERAS=false
CAMERA_ID=4
CAMERA_NAME=Название как на сайте
CAMERA_SOURCE=rtsp://логин:пароль@ip:порт/...
```

`CAMERA_NAME` — то имя, под которым камера будет на дашборде и в heartbeat.

### Несколько камер из БД

```env
USE_MDB_CAMERAS=true
MDB_PARENT_DIR=/home/ВАШ_ПОЛЬЗОВАТЕЛЬ/camera_detect/new2
```

Список RTSP и имён берётся из таблицы **`Cameras`** (`mdb.get_cameras()`). Для каждой строки `id` подставляется в политику **`check_access_rule`**.

### RTSP (если сыпятся ошибки `h264` в консоли)

По очереди попробуйте:

```env
RTSP_TRANSPORT_TCP=true
```

и при необходимости:

```env
RTSP_USE_SNAPSHOT=true
```

### Остальные параметры (можно не менять сначала)

```env
STREAM_INTERVAL_SECONDS=0.5
HEARTBEAT_INTERVAL_SECONDS=5
VIOLATION_COOLDOWN_SECONDS=20
```

---

## 5. Запуск

Активируйте venv и запустите клиент из **каталога `qrpass_client`**:

```bash
cd /home/ВАШ_ПОЛЬЗОВАТЕЛЬ/camera_detect/new2/qrpass_client
source venv/bin/activate
python main.py
```

Графический лаунчер (если установлен `python3-tk`):

```bash
python gui.py
```

В логе не должно быть постоянных **`401`** (неверный токен). Если **`401`** — сверьте `API_TOKEN` с `CLIENT_API_TOKEN` на сервере.

---

## 6. Проверка, что всё доходит до сайта

1. В браузере под админом откройте страницу **статуса / дашборда** — камера с именем из `CAMERA_NAME` или из БД должна стать **«Онлайн»** в течение ~15 секунд.
2. Страница **онлайн-камер** — должен идти поток с объекта.
3. С объекта (опционально):

```bash
curl -s -o /dev/null -w "%{http_code}\n" \
  -H "X-API-Token: ВАШ_API_TOKEN" \
  -X POST -F "camera_name=ИМЯ_КАМЕРЫ" \
  "https://ваш-домен.ru/api/heartbeat"
```

Ожидается **`200`**.

---

## 7. Автозапуск после перезагрузки (по желанию)

Пример **systemd**-юнита под пользователя (пути замените на свои):

```ini
[Unit]
Description=QRPass Client
After=network-online.target

[Service]
Type=simple
User=ВАШ_ПОЛЬЗОВАТЕЛЬ
WorkingDirectory=/home/ВАШ_ПОЛЬЗОВАТЕЛЬ/camera_detect/new2/qrpass_client
EnvironmentFile=/home/ВАШ_ПОЛЬЗОВАТЕЛЬ/camera_detect/new2/qrpass_client/.env
ExecStart=/home/ВАШ_ПОЛЬЗОВАТЕЛЬ/camera_detect/new2/qrpass_client/venv/bin/python main.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
```

```bash
systemctl --user daemon-reload
systemctl --user enable --now qrpass-client.service
```

(имя сервиса и путь к unit-файлу настройте под вашу систему.)

---

## 8. Обновление версии клиента на объекте

1. Остановите процесс (`Ctrl+C` или `systemctl --user stop qrpass-client`).
2. Замените файлы из новой сборки **`qrpass_client`**, **не затирая** свой `.env` и **`venv`** (или сделайте бэкап `.env`).
3. При изменении **`requirements.txt`**: `pip install -r requirements.txt`.
4. Запустите снова.

---

## 9. Частые проблемы

| Симптом | Что проверить |
|--------|----------------|
| **401** на API | `API_TOKEN` = `CLIENT_API_TOKEN`, нет пробелов/кавычек в `.env`. |
| Камера **офлайн** на сайте | `SERVER_URL`, сеть, firewall; heartbeat каждые `HEARTBEAT_INTERVAL_SECONDS`. |
| **`users.db` не найден** / пустые правила | `MDB_PARENT_DIR` указывает на каталог с файлом; после `chdir` процесс видит `users.db`. |
| Нарушения не те | `CAMERA_ID` совпадает с `Cameras.id`; классы совпадают с `POLICY_CLASS_*`; в БД есть строки в **`Rules`** для `POLICY_COLOR_IDS`. |
| Ошибки **SSL** | В `SERVER_URL` именно `https://` и валидный сертификат домена. |

---

## 10. Краткий чеклист перед сдачей объекта

- [ ] `best.pt` на месте, `YOLO_MODEL_PATH` верный.
- [ ] `users.db` актуальна, `Cameras` / `Rules` заполнены.
- [ ] `.env`: `SERVER_URL`, `API_TOKEN`, при обученной модели — `USE_TRAINED_MODEL=true`, `MDB_PARENT_DIR`, при одной камере — `CAMERA_ID`.
- [ ] Клиент запускается без ошибок, на сайте камера **онлайн** и виден поток.
- [ ] Тестовое нарушение (при необходимости) попадает в таблицу на сайте.

Если нужно, добавьте ссылку на этот файл в основной `README.md` проекта.
