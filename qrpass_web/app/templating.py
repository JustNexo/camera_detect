from urllib.parse import quote_plus

from fastapi.templating import Jinja2Templates

from app.camera_scope import DEFAULT_SITE_LABEL
from app.core.config import settings
from app.core.urls import app_url

templates = Jinja2Templates(directory="templates")
templates.env.globals["root_path"] = settings.root_path
templates.env.globals["app_url"] = app_url
templates.env.globals["default_site_label"] = DEFAULT_SITE_LABEL


def stream_live_url(site: str, camera: str) -> str:
    """Параметр site для URL: пустая строка = тот же ключ, что и у клиента без SITE_NAME."""
    s = (site or "").strip()
    if s == DEFAULT_SITE_LABEL:
        s = ""
    q = f"site={quote_plus(s)}&camera={quote_plus(camera)}"
    return app_url(f"/stream/live?{q}")


templates.env.globals["stream_live_url"] = stream_live_url


def stream_snapshot_url(site: str, camera: str) -> str:
    s = (site or "").strip()
    if s == DEFAULT_SITE_LABEL:
        s = ""
    q = f"site={quote_plus(s)}&camera={quote_plus(camera)}"
    return app_url(f"/stream/snapshot?{q}")


templates.env.globals["stream_snapshot_url"] = stream_snapshot_url
