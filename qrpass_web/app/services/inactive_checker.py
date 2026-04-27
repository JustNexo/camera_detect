import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models import CameraPresence, SystemSettings
from app.services.email_service import send_inactive_alert_email
from app.camera_scope import parse_scope_key

logger = logging.getLogger(__name__)

async def check_inactive_pcs_task():
    """
    Фоновая задача: раз в час проверяет, нет ли камер, от которых не было сигнала
    дольше заданного порога (pc_inactive_threshold_hours).
    """
    while True:
        try:
            with SessionLocal() as db:
                _check_inactive_pcs(db)
        except Exception as e:
            logger.error(f"Ошибка в фоновой задаче check_inactive_pcs: {e}")
        
        # Спим 1 час (3600 секунд)
        await asyncio.sleep(3600)

def _check_inactive_pcs(db: Session):
    settings = db.query(SystemSettings).first()
    if not settings or not settings.pc_inactive_alert_enabled:
        return

    threshold_hours = settings.pc_inactive_threshold_hours
    if threshold_hours <= 0:
        return

    now = datetime.now(timezone.utc)
    
    # Ищем все камеры
    cameras = db.query(CameraPresence).all()
    
    for cam in cameras:
        # SQLite может возвращать naive datetime, приводим к UTC
        last_seen = cam.last_seen
        if last_seen.tzinfo is None:
            last_seen = last_seen.replace(tzinfo=timezone.utc)
        else:
            last_seen = last_seen.astimezone(timezone.utc)
            
        inactive_hours = (now - last_seen).total_seconds() / 3600.0
        
        if inactive_hours >= threshold_hours:
            # Проверяем, не отправляли ли мы уже алерт недавно
            # Чтобы не спамить, будем отправлять алерт только если время простоя
            # находится в окне [threshold, threshold + 1 час]
            if inactive_hours < (threshold_hours + 1.0):
                site_name, camera_name = parse_scope_key(cam.scope_key)
                last_seen_str = last_seen.strftime("%Y-%m-%d %H:%M:%S UTC")
                
                logger.warning(f"Алерт неактивности: {site_name} / {camera_name} не на связи {inactive_hours:.1f} ч.")
                
                # Отправляем email в отдельном потоке, чтобы не блокировать цикл
                asyncio.create_task(
                    asyncio.to_thread(
                        send_inactive_alert_email,
                        site_name=site_name,
                        camera_name=camera_name,
                        last_seen=last_seen_str,
                        threshold_hours=threshold_hours,
                        target_email=settings.target_email,
                    )
                )
