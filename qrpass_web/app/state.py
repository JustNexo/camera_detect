from collections import OrderedDict
from datetime import datetime

# Статусы камер в памяти: имя -> время последнего heartbeat/кадра.
camera_status: dict[str, datetime] = {}

# Последний JPEG для MJPEG: scope_key -> bytes. OrderedDict + лимиты в store_latest_frame — иначе RAM растёт с числом камер.
latest_frames: OrderedDict[str, bytes] = OrderedDict()

# Время последнего запроса на просмотр стрима (scope_key -> timestamp).
# Если клиент шлёт heartbeat, а тут свежее время, сервер просит его присылать stream_frame.
active_stream_requests: dict[str, float] = {}

# Человекочитаемое правило по каждой камере (scope_key -> текст правила).
camera_rules: dict[str, str] = {}


def store_latest_frame(key: str, data: bytes) -> bool:
    """Сохранить кадр; False если кадр слишком большой (не пишем в RAM)."""
    from app.core.config import settings

    max_b = max(64 * 1024, int(getattr(settings, "stream_frame_max_bytes", 400 * 1024)))
    max_n = max(1, int(getattr(settings, "stream_frames_max_entries", 48)))
    if len(data) > max_b:
        return False
    latest_frames[key] = data
    latest_frames.move_to_end(key, last=True)
    while len(latest_frames) > max_n:
        latest_frames.popitem(last=False)
    return True
