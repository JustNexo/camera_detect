from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

_engine_kwargs: dict = {}
if settings.database_url.startswith("sqlite"):
    _engine_kwargs["connect_args"] = {"check_same_thread": False, "timeout": 30}

engine = create_engine(settings.database_url, **_engine_kwargs)


@event.listens_for(engine, "connect")
def _sqlite_pragma(dbapi_connection, connection_record):
    if not settings.database_url.startswith("sqlite"):
        return
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=8000")
    cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Все ORM-модели должны быть импортированы до create_all, иначе таблицы не попадут в metadata
# (например при нестандартной точке входа WSGI/тестах).
import app.models.camera_presence  # noqa: E402, F401
import app.models.pig_count_event  # noqa: E402, F401
import app.models.system_settings  # noqa: E402, F401
import app.models.user  # noqa: E402, F401
import app.models.violation  # noqa: E402, F401


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
