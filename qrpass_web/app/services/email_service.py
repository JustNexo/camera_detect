import logging
import smtplib
import ssl
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)

def send_violation_email(
    camera_name: str,
    violation_type: str,
    timestamp: str,
    image_path: str,
    email_enabled: bool,
    target_email: str,
    site_name: str = "",
) -> None:
    # Проверка настроек в БД и SMTP настроек в .env
    to_addr = (target_email or "").strip() or (settings.alert_to_email or "").strip()
    if not email_enabled:
        logger.info("Почта: уведомления выключены в настройках (email_enabled=false).")
        return
    if not to_addr:
        logger.warning("Почта: не задан получатель (target_email в БД или ALERT_TO_EMAIL в .env).")
        return

    if not settings.smtp_host:
        logger.warning("Почта: не задан SMTP_HOST в .env — письмо не отправлено.")
        return
    if not settings.smtp_username or not settings.smtp_password:
        logger.warning("Почта: не заданы SMTP_USERNAME / SMTP_PASSWORD — письмо не отправлено.")
        return

    message = MIMEMultipart("related")
    site_part = f"{site_name} — " if (site_name or "").strip() else ""
    message["Subject"] = f"QRPass: нарушение ({site_part}{camera_name})"
    message["From"] = settings.smtp_from or settings.smtp_username
    message["To"] = to_addr

    html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; background: #f3f4f6; padding: 16px;">
        <div style="max-width: 620px; margin: 0 auto; background: #fff; border: 1px solid #e5e7eb; border-radius: 10px; padding: 18px;">
          <h2 style="margin: 0 0 12px;">QRPass: обнаружено нарушение</h2>
          <p><b>Объект:</b> {(site_name or "").strip() or "—"}</p>
          <p><b>Камера:</b> {camera_name}</p>
          <p><b>Тип:</b> {violation_type}</p>
          <p><b>Время:</b> {timestamp}</p>
          <img src="cid:preview" style="width: 100%; border-radius: 8px; border: 1px solid #d1d5db;" />
        </div>
      </body>
    </html>
    """
    message.attach(MIMEText(html, "html", "utf-8"))

    image_file = Path(image_path)
    if image_file.exists():
        with image_file.open("rb") as file:
            image_mime = MIMEImage(file.read())
            image_mime.add_header("Content-ID", "<preview>")
            image_mime.add_header("Content-Disposition", "inline", filename=image_file.name)
            message.attach(image_mime)

    try:
        if settings.smtp_use_ssl:
            ctx = ssl.create_default_context()
            with smtplib.SMTP_SSL(
                settings.smtp_host, settings.smtp_port, timeout=30, context=ctx
            ) as smtp:
                smtp.login(settings.smtp_username, settings.smtp_password)
                smtp.sendmail(message["From"], [to_addr], message.as_string())
        else:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as smtp:
                if settings.smtp_use_tls:
                    smtp.starttls(context=ssl.create_default_context())
                smtp.login(settings.smtp_username, settings.smtp_password)
                smtp.sendmail(message["From"], [to_addr], message.as_string())
        logger.info("Почта: уведомление о нарушении отправлено на %s", to_addr)
    except OSError as exc:
        logger.exception("Почта: сетевая ошибка SMTP (%s:%s): %s", settings.smtp_host, settings.smtp_port, exc)
    except smtplib.SMTPException as exc:
        logger.exception("Почта: ошибка SMTP: %s", exc)

def send_inactive_alert_email(
    site_name: str,
    camera_name: str,
    last_seen: str,
    threshold_hours: int,
    target_email: str,
) -> None:
    to_addr = (target_email or "").strip() or (settings.alert_to_email or "").strip()
    if not to_addr:
        logger.warning("Почта (неактивность): не задан получатель.")
        return

    if not settings.smtp_host or not settings.smtp_username or not settings.smtp_password:
        logger.warning("Почта (неактивность): не заданы SMTP настройки.")
        return

    message = MIMEMultipart("alternative")
    site_part = f"{site_name} — " if (site_name or "").strip() else ""
    message["Subject"] = f"ВНИМАНИЕ: Потеряна связь с объектом ({site_part}{camera_name})"
    message["From"] = settings.smtp_from or settings.smtp_username
    message["To"] = to_addr

    html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; background: #fef2f2; padding: 16px;">
        <div style="max-width: 620px; margin: 0 auto; background: #fff; border: 1px solid #fca5a5; border-radius: 10px; padding: 18px;">
          <h2 style="margin: 0 0 12px; color: #dc2626;">Потеряна связь с мини-ПК</h2>
          <p>Система не получает сигналы (heartbeat) от оборудования дольше заданного порога ({threshold_hours} ч.).</p>
          <p>Возможно, на объекте отключилось электричество или пропал интернет.</p>
          <hr style="border: 0; border-top: 1px solid #fca5a5; margin: 16px 0;">
          <p><b>Объект:</b> {(site_name or "").strip() or "—"}</p>
          <p><b>Камера (источник):</b> {camera_name}</p>
          <p><b>Последний сигнал был:</b> {last_seen}</p>
        </div>
      </body>
    </html>
    """
    message.attach(MIMEText(html, "html", "utf-8"))

    try:
        if settings.smtp_use_ssl:
            ctx = ssl.create_default_context()
            with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=30, context=ctx) as smtp:
                smtp.login(settings.smtp_username, settings.smtp_password)
                smtp.sendmail(message["From"], [to_addr], message.as_string())
        else:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as smtp:
                if settings.smtp_use_tls:
                    smtp.starttls(context=ssl.create_default_context())
                smtp.login(settings.smtp_username, settings.smtp_password)
                smtp.sendmail(message["From"], [to_addr], message.as_string())
        logger.info("Почта (неактивность): алерт отправлен на %s", to_addr)
    except Exception as exc:
        logger.exception("Почта (неактивность): ошибка отправки: %s", exc)
