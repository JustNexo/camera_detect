from sqlalchemy import Column, DateTime, Float, Integer, String

from app.core.database import Base


class PigCountEvent(Base):
    __tablename__ = "pig_count_events"

    id = Column(Integer, primary_key=True, index=True)
    site_name = Column(String(256), nullable=False, default="")
    camera_name = Column(String(256), nullable=False)
    direction = Column(String(16), nullable=False, default="up")
    line_y_ratio = Column(Float, nullable=False, default=0.58)
    count = Column(Integer, nullable=False, default=0)
    ts_from = Column(DateTime(timezone=True), nullable=False)
    ts_to = Column(DateTime(timezone=True), nullable=False)
    preview_path = Column(String(1024), nullable=False, default="")
    created_at = Column(DateTime(timezone=True), nullable=False)
