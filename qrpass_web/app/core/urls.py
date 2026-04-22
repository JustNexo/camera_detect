"""Построение URL с учётом ROOT_PATH (сайт в подкаталоге, например /qrpass_web)."""
from app.core.config import settings


def app_url(path: str) -> str:
    path = path.strip() or "/"
    if not path.startswith("/"):
        path = "/" + path
    base = settings.root_path
    if not base:
        return path
    return f"{base.rstrip('/')}{path}"
