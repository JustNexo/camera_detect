from sqlalchemy import Column, DateTime, Integer, String

from app.core.database import Base


class CameraPresence(Base):
    """Последний heartbeat/кадр по камере — общее состояние для всех WSGI-воркеров."""

    __tablename__ = "camera_presence"

    id = Column(Integer, primary_key=True, index=True)
    scope_key = Column(String(512), unique=True, nullable=False, index=True)
    last_seen = Column(DateTime(timezone=True), nullable=False)
    rule_summary = Column(String(2048), nullable=False, default="", server_default="")
