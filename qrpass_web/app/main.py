from pathlib import Path
import logging
import random
from datetime import datetime, timedelta, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.core.config import settings
from sqlalchemy import text

from app.camera_scope import scope_key
from app.core.database import Base, engine, SessionLocal
from app.models import CameraPresence, SystemSettings, Violation
from app.middleware.error_dump import DumpErrorsMiddleware, write_startup_probe
from app.routers import api, auth, pages, stream

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    write_startup_probe()
    # Инициализация БД и демо-данных
    Path("static/violations").mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    # На существующих БД иногда не подхватывалась новая таблица — дублируем с checkfirst.
    CameraPresence.__table__.create(bind=engine, checkfirst=True)

    if settings.database_url.startswith("sqlite"):
        with engine.begin() as conn:
            rows = conn.execute(text("PRAGMA table_info(violations)")).fetchall()
            col_names = {row[1] for row in rows}
            if "site_name" not in col_names:
                conn.execute(text("ALTER TABLE violations ADD COLUMN site_name VARCHAR(256) NOT NULL DEFAULT ''"))

    with SessionLocal() as db:
        # Проверка и создание настроек по умолчанию
        if db.query(SystemSettings).count() == 0:
            db.add(SystemSettings(email_enabled=True, target_email="admin@qrpass.local"))
            db.commit()

        # Одна демо-запись в истории (только если SEED_DEMO_DATA=true и таблица пустая)
        if settings.seed_demo_data and db.query(Violation).count() == 0:
            now = datetime.now(timezone.utc)
            v = Violation(
                timestamp=now - timedelta(minutes=12),
                site_name="Демо-площадка",
                camera_name="ФФО-1",
                violation_type="Нет униформы",
                image_path="https://placehold.co/600x400/eeeeee/4b5563?text=Demo+Photo",
            )
            db.add(v)
            db.commit()

    # Предзаполнение heartbeat для демо-камер в БД (только если SEED_DEMO_DATA=true)
    if settings.seed_demo_data:
        now = datetime.now(timezone.utc)
        demo_pairs = [
            ("Площадка А", "ФФО-1"),
            ("Площадка А", "ФФО-2"),
            ("Площадка А", "ФФО-3"),
            ("Площадка А", "ФФО-4"),
            ("Площадка Б", "ТР-1"),
            ("Площадка Б", "ТР-2"),
            ("Площадка Б", "ТР-3"),
            ("Площадка Б", "ТР-4"),
        ]
        with SessionLocal() as db:
            for site, cam in demo_pairs:
                sk = scope_key(site, cam)
                if cam == "ТР-4":
                    seen = now - timedelta(minutes=5)
                else:
                    seen = now - timedelta(seconds=random.randint(1, 3))
                row = db.query(CameraPresence).filter(CameraPresence.scope_key == sk).first()
                if not row:
                    db.add(
                        CameraPresence(
                            scope_key=sk,
                            last_seen=seen,
                            rule_summary="Демо: правило не задано",
                        )
                    )
            db.commit()

    pd = int(settings.camera_presence_prune_days or 0)
    if pd > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(days=pd)
        with SessionLocal() as db:
            n = db.query(CameraPresence).filter(CameraPresence.last_seen < cutoff).delete(
                synchronize_session=False
            )
            db.commit()
        if n:
            logging.info("Удалено %s устаревших строк camera_presence (last_seen старше %s дн.)", n, pd)

    yield
    # Очистка ресурсов при остановке (если нужна)


app = FastAPI(title=settings.app_name, lifespan=lifespan)
# HTTP без SSL: cookie без флага Secure; при подкаталоге — path для сессии
_session_path = settings.root_path if settings.root_path else "/"
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    max_age=60 * 60 * 24,
    https_only=False,
    path=_session_path,
)

_rp = settings.root_path or ""
_static = f"{_rp}/static".replace("//", "/") if _rp else "/static"
app.mount(_static, StaticFiles(directory="static"), name="static")

app.include_router(auth.router, prefix=_rp)
app.include_router(pages.router, prefix=_rp)
app.include_router(api.router, prefix=_rp)
app.include_router(stream.router, prefix=_rp)

# Самый внешний слой: любое исключение в роуте/Depends/части сессии -> qrpass_last_error.log
app.add_middleware(DumpErrorsMiddleware)
