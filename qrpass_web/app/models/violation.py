from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.sql import func

from app.core.database import Base


class Violation(Base):
    __tablename__ = "violations"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    site_name = Column(String(256), nullable=False, default="", server_default="")
    camera_name = Column(String(128), nullable=False)
    violation_type = Column(String(128), nullable=False)
    image_path = Column(String(255), nullable=False)
