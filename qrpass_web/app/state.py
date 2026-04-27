import hashlib
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
import time

# Статусы камер в памяти
camera_status: dict[str, datetime] = {}
camera_rules: dict[str, str] = {}

STREAMS_DIR = Path("static/streams")
try:
    STREAMS_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    pass

def _safe_key(key: str) -> str:
    return hashlib.md5(key.encode('utf-8')).hexdigest()

def store_latest_frame(key: str, data: bytes) -> bool:
    """Сохранить кадр на диск, чтобы разные воркеры uWSGI видели его."""
    from app.core.config import settings
    max_b = max(64 * 1024, int(getattr(settings, "stream_frame_max_bytes", 400 * 1024)))
    if len(data) > max_b:
        return False
    try:
        f = STREAMS_DIR / f"{_safe_key(key)}.jpg"
        f.write_bytes(data)
        return True
    except Exception:
        return False

def get_latest_frame(key: str) -> bytes | None:
    try:
        f = STREAMS_DIR / f"{_safe_key(key)}.jpg"
        if f.exists():
            return f.read_bytes()
    except Exception:
        pass
    return None

def mark_stream_requested(key: str) -> None:
    try:
        f = STREAMS_DIR / f"{_safe_key(key)}.req"
        f.touch(exist_ok=True)
    except Exception:
        pass

def is_stream_requested(key: str, timeout: float = 20.0) -> bool:
    try:
        f = STREAMS_DIR / f"{_safe_key(key)}.req"
        if time.time() - f.stat().st_mtime < timeout:
            return True
    except Exception:
        pass
    return False
