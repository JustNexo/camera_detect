import os
from pathlib import Path

from dotenv import load_dotenv

# Корень проекта: app/core/config.py -> на два уровня вверх = app/, ещё один = qrpass_web/
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
# На uWSGI/Apache cwd часто не совпадает с каталогом проекта — грузим .env по абсолютному пути.
load_dotenv(_PROJECT_ROOT / ".env")
load_dotenv()


def _env_bool(key: str, default: bool) -> bool:
    raw = os.getenv(key)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _normalize_root_path(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        return ""
    if not raw.startswith("/"):
        raw = "/" + raw
    return raw.rstrip("/") or ""


class Settings:
    app_name: str = os.getenv("APP_NAME", "QRPass")
    secret_key: str = os.getenv("SECRET_KEY", "change_me")
    # Если сайт открывается как https://домен/qrpass_web/ — задайте ROOT_PATH=/qrpass_web
    root_path: str = _normalize_root_path(os.getenv("ROOT_PATH", ""))
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./qrpass_web.db")
    client_api_token: str = os.getenv("CLIENT_API_TOKEN", "change_me_api_token")
    # На продакшене (Sprinthost) установите SEED_DEMO_DATA=false — без демо-нарушений и фейкового heartbeat.
    seed_demo_data: bool = _env_bool("SEED_DEMO_DATA", True)

    smtp_host: str = os.getenv("SMTP_HOST", "")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_username: str = os.getenv("SMTP_USERNAME", "")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")
    smtp_from: str = os.getenv("SMTP_FROM", "")
    smtp_use_tls: bool = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
    # Порт 465: обычно SSL с самого начала (SMTP_SSL), не STARTTLS.
    smtp_use_ssl: bool = _env_bool("SMTP_USE_SSL", False)
    alert_to_email: str = os.getenv("ALERT_TO_EMAIL", "")
    # Временно true на хостинге — показывать текст исключения на странице логина (потом выключить).
    show_login_errors: bool = _env_bool("SHOW_LOGIN_ERRORS", False)
    # Доп. каталог для логов ошибок (доступен на запись веб-процессу), например /tmp или ~/logs
    error_log_dir: str = (os.getenv("ERROR_LOG_DIR", "") or "").strip()
    # Считаем камеру «онлайн», если last_seen не старше N секунд (KPI /cameras /dashboard).
    camera_online_seconds: int = int(os.getenv("CAMERA_ONLINE_SECONDS", "20"))
    # 0 = выкл. Иначе при старте удаляются строки camera_presence с last_seen старше N дней
    # («призраки» после смены имён камер; новые снова появятся с heartbeat).
    camera_presence_prune_days: int = int(os.getenv("CAMERA_PRESENCE_PRUNE_DAYS", "0") or 0)
    # Лимиты RAM: JPEG в памяти на /stream (см. app.state.latest_frames)
    stream_frame_max_bytes: int = int(os.getenv("STREAM_FRAME_MAX_BYTES", str(400 * 1024)))
    stream_frames_max_entries: int = int(os.getenv("STREAM_FRAMES_MAX_ENTRIES", "48"))
    # Дашборд: сколько строк истории поднимать из БД (меньше — меньше памяти на запрос).
    dashboard_violations_limit: int = int(os.getenv("DASHBOARD_VIOLATIONS_LIMIT", "80"))
    # POST /api/violation: макс. размер файла нарушения (байты).
    violation_upload_max_bytes: int = int(os.getenv("VIOLATION_UPLOAD_MAX_BYTES", str(6 * 1024 * 1024)))


settings = Settings()
