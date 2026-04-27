from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env")
load_dotenv()


def _f(name: str, default: str = "") -> str:
    return (os.getenv(name, default) or "").strip()


def _i(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)) or default)
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)) or default)
    except ValueError:
        return default


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


class EdgeSettings:
    queue_db_path: Path = Path(_f("QUEUE_DB_PATH", str(_ROOT / "data" / "edge_queue.db")))
    storage_root: Path = Path(_f("STORAGE_ROOT", str(_ROOT / "data" / "violations")))
    storage_max_gb: float = _float("STORAGE_MAX_GB", 0.0)

    server_url: str = _f("SERVER_URL", "http://127.0.0.1:8000").rstrip("/")
    api_token: str = _f("API_TOKEN", "")
    site_name: str = _f("SITE_NAME", "")

    edge_ui_host: str = _f("EDGE_UI_HOST", "127.0.0.1")
    edge_ui_port: int = _i("EDGE_UI_PORT", 8088)

    agent_poll_seconds: float = _float("AGENT_POLL_SECONDS", 5.0)
    heartbeat_interval_seconds: float = _float("HEARTBEAT_INTERVAL_SECONDS", 10.0)
    default_camera_name: str = _f("DEFAULT_CAMERA_NAME", "EDGE-CAM-1")
    heartbeat_error_log_cooldown_seconds: float = _float("HEARTBEAT_ERROR_LOG_COOLDOWN_SECONDS", 60.0)
    camera_online_seconds: int = _i("CAMERA_ONLINE_SECONDS", 20)
    upstream_enabled: bool = _bool("UPSTREAM_ENABLED", True)
    upstream_stream_enabled: bool = _bool("UPSTREAM_STREAM_ENABLED", True)
    client_service_name: str = _f("CLIENT_SERVICE_NAME", "qrpass-client.service")
    client_process_pattern: str = _f("CLIENT_PROCESS_PATTERN", "qrpass_client/main.py")
    log_file_path: Path = Path(_f("LOG_FILE_PATH", "/var/lib/qrpass/edge.log"))
    log_max_mb: int = _i("LOG_MAX_MB", 20)
    log_backups: int = _i("LOG_BACKUPS", 5)
    kiosk_unlock_file: Path = Path(_f("KIOSK_UNLOCK_FILE", "/etc/qrpass/kiosk.unlock"))


settings = EdgeSettings()
