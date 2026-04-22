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
    last_sent_at = 0.0
    while True:
        k = _resolve_frame_key(frame_key)
        active_stream_requests[k or frame_key] = time.time()
        frame = latest_frames.get(k) if k else None
        now = time.monotonic()
        should_send = False
        if frame:
            # 1) Новый JPEG отправляем сразу.
            # 2) Тот же JPEG шлём как keepalive раз в STREAM_KEEPALIVE_SECONDS.
            if frame != last_sent_frame:
                should_send = True
            elif now - last_sent_at >= STREAM_KEEPALIVE_SECONDS:
                should_send = True
        if should_send:
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
            last_sent_frame = frame
            last_sent_at = now
        await asyncio.sleep(STREAM_OUTPUT_INTERVAL)


@router.get("/stream/live")
async def camera_stream_live(
    site: str = Query("", description="Объект / площадка"),
    camera: str = Query(..., description="Имя камеры"),
    _: object = Depends(get_current_user),
):
    key = scope_key(site, camera)
    if _resolve_frame_key(key) is None:
        raise HTTPException(status_code=404, detail="Поток камеры пока недоступен")
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
    if _resolve_frame_key(camera_name) is None:
        raise HTTPException(status_code=404, detail="Поток камеры пока недоступен")
    return StreamingResponse(
        stream_generator(scope_key("", camera_name)),
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
    k = _resolve_frame_key(key)
    active_stream_requests[k or key] = time.time()
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
