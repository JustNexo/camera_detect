from sqlalchemy import Boolean, Column, Integer, String

from app.core.database import Base


class SystemSettings(Base):
    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True, index=True)
    email_enabled = Column(Boolean, default=True, nullable=False)
    target_email = Column(String(255), default="admin@qrpass.local", nullable=False)
    # Настройки для контроля активности ПК (пункт 9.1)
    pc_inactive_alert_enabled = Column(Boolean, default=False, nullable=False)
    pc_inactive_threshold_hours = Column(Integer, default=24, nullable=False)
