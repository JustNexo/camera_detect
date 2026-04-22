# QRPass Web (хостинг)

## Переменные окружения (продакшен)

| Переменная | Описание |
|------------|----------|
| `SECRET_KEY` | Секрет для сессий (длинная случайная строка). |
| `DATABASE_URL` | SQLite: `sqlite:////абсолютный/путь/qrpass_web.db` на хостинге (файл должен быть доступен на запись процессу веб-сервера). |
| `CLIENT_API_TOKEN` | Общий секрет для API (`X-API-Token`) — тот же задаётся на edge-клиенте. |
| `SEED_DEMO_DATA` | `false` на продакшене — без демо-нарушений и без фейковых статусов камер. `true` удобно для локальной демонстрации. |
| SMTP (`SMTP_*`, `ALERT_TO_EMAIL`) | Опционально для почты из `.env`; адрес получателя в UI настраивается в «Настройках» (`SystemSettings`). |

Скопируйте [`.env.example`](.env.example) в `.env` и заполните значения.

## Локальная установка

```bash
pip install -r requirements.txt
```

## Создание администратора

```bash
python scripts/create_admin.py --username admin --password ВАШ_ПАРОЛЬ
```

## Локальный запуск (разработка)

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## Развёртывание на Sprinthost (shared, Python / uWSGI)

1. Загрузите каталог проекта на сервер (SSH / SFTP), например `~/domains/ВАШ_ДОМЕН/qrpass_web/`.
2. По SSH: создайте виртуальное окружение, установите зависимости:
   ```bash
   cd ~/domains/ВАШ_ДОМЕН/qrpass_web
   python3 -m venv venv
   source venv/bin/activate
   python -m pip install --upgrade pip setuptools wheel
   pip install --prefer-binary -r requirements.txt
   ```
   **Если падает сборка `greenlet` (ошибка `g++`, `Failed building wheel for greenlet`):**  
   `pip` не нашёл готовый wheel под вашу связку Python/ОС и полез в компиляцию (на shared часто нет нормального toolchain). Делайте по шагам:

   1. Убедитесь, что активирован тот же `python3`, что выбран для сайта в панели (часто **3.10 или 3.11** — у них больше готовых wheels, чем у 3.12+).
   2. Принудительно только бинарники для greenlet, затем остальное:
      ```bash
      pip install greenlet --only-binary :all:
      pip install --prefer-binary -r requirements.txt
      ```
   3. В **pip 23+** можно заранее задать переменную (Linux/macOS):
      ```bash
      export PIP_ONLY_BINARY=greenlet
      pip install --prefer-binary -r requirements.txt
      ```
   4. Если `greenlet --only-binary` пишет, что подходящего wheel нет — смените версию Python в панели хостинга на **3.10/3.11** и пересоздайте `venv`. Либо скачайте на своём ПК wheel под ту же версию Python и платформу (`manylinux`) и установите файл через `pip install ./greenlet-...whl`.

   В крайнем случае — тикет в поддержку (нужны компилятор и заголовки Python) или **VDS** с `python3-dev` и `build-essential`.
3. Положите `.env` в корень проекта. Обязательно: `SEED_DEMO_DATA=false`, сильные `SECRET_KEY` и `CLIENT_API_TOKEN`, путь к SQLite с правами на запись.
4. В панели Sprinthost для сайта выберите обработку Python через **uWSGI** (см. [базу знаний: Python](https://help.sprinthost.ru/howto/python)).
5. Укажите файл входа **WSGI**: [`wsgi.py`](wsgi.py) в корне проекта (если панель требует имя `site.wsgi`, скопируйте `wsgi.py` под этим именем или сделайте симлинк).
6. Настройте `.htaccess` в корне сайта по инструкции хостинга; ориентир — [deploy/sprinthost.htaccess.example](deploy/sprinthost.htaccess.example).
7. Включите HTTPS (SSL) для домена.
8. **После любой заливки `.py` перезапустите Python/uWSGI** (в панели Sprinthost — «перезапуск приложения» / смена режима и обратно, либо тикет). Обычно процесс **сам не подхватывает** новый код; без перезапуска вы продолжаете видеть старые ошибки (в т.ч. с паролем). Проверка: `GET /api/_debug/selfcheck` с заголовком `X-API-Token` — в ответе должно быть `"password_security": { "hash_long_password_ok": true, "backend": "bcrypt_native", ... }`.
9. Один раз создайте админа (из каталога проекта, с активированным venv):
   ```bash
   python scripts/create_admin.py --username admin --password '...'
   ```

Если uWSGI + ASGI-обёртка (`a2wsgi`) работает нестабильно, рассмотрите VDS (Sprinbox) и запуск `uvicorn`/`gunicorn` под своим процессом — см. общие инструкции по FastAPI.

### `OSError: [Errno 14] Bad address` при импорте SQLAlchemy

Часто это **битый байткод** (`__pycache__`) или кэш pip на сетевой ФС. По SSH из каталога проекта:

```bash
find . -type d -name __pycache__ -prune -exec rm -rf {} +
source venv/bin/activate
pip install --no-cache-dir --force-reinstall sqlalchemy
```

Затем перезапуск приложения в панели. В [`wsgi.py`](wsgi.py) включено `PYTHONDONTWRITEBYTECODE` для новых импортов через WSGI.

## Страницы

- `/login` — вход
- `/dashboard` — главная, нарушения
- `/cameras` — онлайн-потоки (`/stream/{имя_камеры}`)
- `/status` — статус Heartbeat
- `/settings` — email и оповещения

## API для edge-клиента (токен `X-API-Token`)

- `POST /api/heartbeat`
- `POST /api/stream_frame`
- `POST /api/violation`

## Проверка после деплоя (smoke)

1. Браузер: `https://ВАШ_ДОМЕН/login` — страница входа без 500.
2. Вход под админом — `/dashboard` открывается.
3. С объекта: запущен `qrpass_client` с `SERVER_URL` и тем же `API_TOKEN`, что `CLIENT_API_TOKEN` на сервере — на `/status` камера «Онлайн».
4. `/cameras` — виден MJPEG-поток для камеры, которая шлёт кадры.
5. При тестовом нарушении — новая строка в таблице нарушений (и письмо, если SMTP и настройки в «Настройках» включены).
