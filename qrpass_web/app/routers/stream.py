import asyncio
import threading
import time

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response, StreamingResponse

from app.camera_scope import scope_key
from app.core.config import settings
from app.core.security import get_current_user
from app.state import get_latest_frame, mark_stream_requested

router = APIRouter(tags=["stream"])
STREAM_OUTPUT_FPS = 2.0
STREAM_OUTPUT_INTERVAL = 1.0 / STREAM_OUTPUT_FPS
# Даже если кадр не меняется побайтно, периодически пересылаем его,
# чтобы браузер не "замирал" на одном JPEG до ручного обновления.
STREAM_KEEPALIVE_SECONDS = 1.5
_stream_lock = threading.Lock()
_active_streams = 0


def _try_acquire_stream_slot() -> bool:
    global _active_streams
    with _stream_lock:
        if _active_streams >= max(1, int(settings.stream_live_max_connections)):
            return False
        _active_streams += 1
        return True


def _release_stream_slot() -> None:
    global _active_streams
    with _stream_lock:
        _active_streams = max(0, _active_streams - 1)


async def stream_generator(frame_key: str, request: Request):
    last_sent_frame: bytes | None = None
    last_sent_at = time.monotonic()
    started_at = time.monotonic()
    
    # Сразу шлём заголовок multipart, чтобы uWSGI/Nginx не отвалились по таймауту (502)
    yield b"--frame\r\n"
    
    try:
        while True:
            # Защитный TTL: ограничиваем жизнь каждого long-lived stream.
            if (time.monotonic() - started_at) >= max(30, int(settings.stream_live_max_seconds)):
                break
            # Явная проверка разрыва клиента: защищает от залипания воркеров uWSGI.
            if await request.is_disconnected():
                break

            # Отмечаем, что этот стрим всё ещё ждут
            mark_stream_requested(frame_key)

            # Читаем кадр с диска (расшарено между всеми воркерами uWSGI)
            frame = get_latest_frame(frame_key)
            now = time.monotonic()

            if frame and frame != last_sent_frame:
                # Новый кадр
                yield b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n--frame\r\n"
                last_sent_frame = frame
                last_sent_at = now
            elif now - last_sent_at >= STREAM_KEEPALIVE_SECONDS:
                # keepalive чтобы прокси не рвали молча долгие соединения
                yield b"Content-Type: text/plain\r\n\r\n\r\n--frame\r\n"
                last_sent_at = now

            await asyncio.sleep(STREAM_OUTPUT_INTERVAL)
    except asyncio.CancelledError:
        # Нормальное завершение при закрытии вкладки/сокета.
        return


async def stream_generator_with_slot(frame_key: str, request: Request):
    try:
        async for chunk in stream_generator(frame_key, request):
            yield chunk
    finally:
        _release_stream_slot()


@router.get("/stream/live")
async def camera_stream_live(
    request: Request,
    site: str = Query("", description="Объект / площадка"),
    camera: str = Query(..., description="Имя камеры"),
    _: object = Depends(get_current_user),
):
    if not _try_acquire_stream_slot():
        raise HTTPException(
            status_code=429,
            detail="Слишком много одновременных live-stream подключений. Повторите позже.",
        )
    key = scope_key(site, camera)
    # Удаляем проверку на 404, чтобы соединение "зависло" в ожидании первого кадра (on-demand streaming)
    return StreamingResponse(
        stream_generator_with_slot(key, request),
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
async def camera_stream_legacy(
    camera_name: str,
    request: Request,
    _: object = Depends(get_current_user),
):
    """Совместимость: старый URL с одним сегментом = только имя камеры (без объекта)."""
    if not _try_acquire_stream_slot():
        raise HTTPException(
            status_code=429,
            detail="Слишком много одновременных live-stream подключений. Повторите позже.",
        )
    key = scope_key("", camera_name)
    return StreamingResponse(
        stream_generator_with_slot(key, request),
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
    mark_stream_requested(key)
    
    # Ждём до 5 секунд, если кадра ещё нет
    for _ in range(10):
        frame = get_latest_frame(key)
        if frame:
            break
        await asyncio.sleep(0.5)
        
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
