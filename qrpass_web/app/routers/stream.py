import asyncio
import time

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response, StreamingResponse

from app.camera_scope import scope_key
from app.core.security import get_current_user
from app.state import latest_frames, active_stream_requests

router = APIRouter(tags=["stream"])
STREAM_OUTPUT_FPS = 2.0
STREAM_OUTPUT_INTERVAL = 1.0 / STREAM_OUTPUT_FPS
# Даже если кадр не меняется побайтно, периодически пересылаем его,
# чтобы браузер не "замирал" на одном JPEG до ручного обновления.
STREAM_KEEPALIVE_SECONDS = 1.5


def _resolve_frame_key(raw: str) -> str | None:
    """Найти ключ в latest_frames: полный JSON-ключ или legacy (только имя камеры)."""
    if raw in latest_frames:
        return raw
    legacy = scope_key(None, raw)
    if legacy in latest_frames:
        return legacy
    return None


async def stream_generator(frame_key: str):
    last_sent_frame: bytes | None = None
    last_sent_at = time.monotonic()
    
    # Сразу шлём заголовок multipart, чтобы uWSGI/Nginx не отвалились по таймауту (502)
    yield b"--frame\r\n"
    
    while True:
        k = _resolve_frame_key(frame_key)
        active_stream_requests[k or frame_key] = time.time()
        frame = latest_frames.get(k) if k else None
        now = time.monotonic()
        
        should_send = False
        if frame and frame != last_sent_frame:
            # Новый кадр
            yield b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n--frame\r\n"
            last_sent_frame = frame
            last_sent_at = now
        elif now - last_sent_at >= STREAM_KEEPALIVE_SECONDS:
            # Важно: шлём пустой блок, если нет кадров! 
            # Иначе WSGI-воркер "зависает" навсегда и не понимает, что клиент закрыл вкладку (Deadlock)
            yield b"Content-Type: text/plain\r\n\r\n\r\n--frame\r\n"
            last_sent_at = now
            
        await asyncio.sleep(STREAM_OUTPUT_INTERVAL)


@router.get("/stream/live")
async def camera_stream_live(
    site: str = Query("", description="Объект / площадка"),
    camera: str = Query(..., description="Имя камеры"),
    _: object = Depends(get_current_user),
):
    key = scope_key(site, camera)
    # Удаляем проверку на 404, чтобы соединение "зависло" в ожидании первого кадра (on-demand streaming)
    return StreamingResponse(
        stream_generator(key),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
            # Для Nginx/прокси: не буферизовать поток MJPEG.
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/stream/{camera_name:path}")
async def camera_stream_legacy(camera_name: str, _: object = Depends(get_current_user)):
    """Совместимость: старый URL с одним сегментом = только имя камеры (без объекта)."""
    key = scope_key("", camera_name)
    return StreamingResponse(
        stream_generator(key),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/stream/snapshot")
async def camera_snapshot(
    site: str = Query("", description="Объект / площадка"),
    camera: str = Query(..., description="Имя камеры"),
    _: object = Depends(get_current_user),
):
    """Один JPEG-кадр для polling в браузере (устойчиво на shared hosting)."""
    key = scope_key(site, camera)
    
    # Отмечаем, что кто-то смотрит (клиент получит команду начать стрим в следующем heartbeat)
    active_stream_requests[_resolve_frame_key(key) or key] = time.time()
    
    # Ждём до 5 секунд, если кадра ещё нет
    for _ in range(10):
        k = _resolve_frame_key(key)
        if k and latest_frames.get(k):
            break
        await asyncio.sleep(0.5)
        
    k = _resolve_frame_key(key)
    if k is None:
        raise HTTPException(status_code=404, detail="Кадр камеры пока недоступен")
    frame = latest_frames.get(k)
    if not frame:
        raise HTTPException(status_code=404, detail="Кадр камеры пока недоступен")
    return Response(
        content=frame,
        media_type="image/jpeg",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )
