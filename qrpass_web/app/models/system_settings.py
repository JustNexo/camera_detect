from sqlalchemy import Boolean, Column, Integer, String

from app.core.database import Base


class SystemSettings(Base):
    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True, index=True)
    email_enabled = Column(Boolean, default=True, nullable=False)
    target_email = Column(String(255), default="admin@qrpass.local", nullable=False)
