from collections import defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import RedirectResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.camera_scope import DEFAULT_SITE_LABEL, normalize_site_for_display, parse_scope_key
from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.core.urls import app_url
from app.models import CameraPresence, PigCountEvent, User, Violation, SystemSettings
from app.templating import templates

router = APIRouter(tags=["pages"])


def normalize_to_utc(dt: datetime) -> datetime:
    # SQLite часто возвращает naive datetime, поэтому явно приводим к UTC.
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _site_query_param_for_stream(parsed_site: str) -> str:
    if parsed_site == DEFAULT_SITE_LABEL:
        return ""
    return parsed_site


def build_site_camera_tree(db: Session):
    """Группировка камер по объекту + флаги онлайн (из БД, общая для всех воркеров)."""
    now = datetime.now(timezone.utc)
    online_sec = max(5, int(getattr(settings, "camera_online_seconds", 20)))
    by_site: dict[str, list[dict]] = defaultdict(list)

    rows = db.query(CameraPresence).all()
    for row in rows:
        scope_key_str = row.scope_key
        site_part, cam_part = parse_scope_key(scope_key_str)
        site_d = normalize_site_for_display(site_part)
        seen = row.last_seen
        seen_utc = normalize_to_utc(seen)
        delta = (now - seen_utc).total_seconds()
        by_site[site_d].append(
            {
                "scope_key": scope_key_str,
                "camera_name": cam_part,
                "site_display": site_d,
                "stream_site": _site_query_param_for_stream(site_d),
                "last_seen": seen.strftime("%Y-%m-%d %H:%M:%S"),
                "is_online": delta < online_sec,
                "rule_summary": (row.rule_summary or "").strip() or "Правило не передано",
            }
        )

    sites_out = []
    for site_name in sorted(by_site.keys()):
        cams = sorted(by_site[site_name], key=lambda x: x["camera_name"].lower())
        online_c = sum(1 for c in cams if c["is_online"])
        n = len(cams)
        sites_out.append(
            {
                "name": site_name,
                "cameras": cams,
                "online_count": online_c,
                "total": n,
                "all_online": n > 0 and online_c == n,
                "all_offline": n > 0 and online_c == 0,
            }
        )
    return sites_out


@router.get("/")
def root_redirect(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse(url=app_url("/dashboard"), status_code=303)
    return RedirectResponse(url=app_url("/login"), status_code=303)


@router.get("/dashboard")
def dashboard(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lim = max(10, min(500, int(getattr(settings, "dashboard_violations_limit", 80))))
    violations = db.query(Violation).order_by(Violation.timestamp.desc()).limit(lim).all()

    # Расчет метрик (KPI)
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_violations_count = (
        db.query(func.count(Violation.id)).filter(Violation.timestamp >= today_start).scalar() or 0
    )

    online_sec = max(5, int(getattr(settings, "camera_online_seconds", 20)))
    pres = db.query(CameraPresence).all()
    active_cameras_count = sum(
        1 for p in pres if (now - normalize_to_utc(p.last_seen)).total_seconds() < online_sec
    )
    attention_cameras_count = sum(
        1 for p in pres if (now - normalize_to_utc(p.last_seen)).total_seconds() >= online_sec
    )

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "user": current_user,
            "violations": violations,
            "today_violations_count": today_violations_count,
            "active_cameras_count": active_cameras_count,
            "attention_cameras_count": attention_cameras_count,
        },
    )


@router.get("/cameras")
def cameras_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sites = build_site_camera_tree(db)
    default_stream_site = ""
    default_camera = ""
    if sites and sites[0]["cameras"]:
        c0 = sites[0]["cameras"][0]
        default_stream_site = c0["stream_site"]
        default_camera = c0["camera_name"]

    return templates.TemplateResponse(
        request,
        "cameras.html",
        {
            "user": current_user,
            "sites": sites,
            "default_stream_site": default_stream_site,
            "default_camera": default_camera,
        },
    )


@router.get("/status")
def status_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sites = build_site_camera_tree(db)
    return templates.TemplateResponse(
        request,
        "status.html",
        {"user": current_user, "sites": sites},
    )


@router.get("/pig-count")
def pig_count_page(
    request: Request,
    date_from: str = "",
    date_to: str = "",
    site_name: str = "",
    camera_name: str = "",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(PigCountEvent)
    if site_name.strip():
        q = q.filter(PigCountEvent.site_name == site_name.strip())
    if camera_name.strip():
        q = q.filter(PigCountEvent.camera_name == camera_name.strip())
    if date_from.strip():
        try:
            dt_from = datetime.strptime(date_from.strip(), "%Y-%m-%d").replace(tzinfo=timezone.utc)
            q = q.filter(PigCountEvent.ts_to >= dt_from)
        except ValueError:
            pass
    if date_to.strip():
        try:
            dt_to = datetime.strptime(date_to.strip(), "%Y-%m-%d").replace(tzinfo=timezone.utc)
            dt_to = dt_to.replace(hour=23, minute=59, second=59)
            q = q.filter(PigCountEvent.ts_from <= dt_to)
        except ValueError:
            pass
    events = q.order_by(PigCountEvent.ts_to.desc()).limit(500).all()
    total_count = sum(int(e.count or 0) for e in events)

    return templates.TemplateResponse(
        request,
        "pig_count.html",
        {
            "user": current_user,
            "events": events,
            "total_count": total_count,
            "date_from": date_from,
            "date_to": date_to,
            "site_name": site_name,
            "camera_name": camera_name,
        },
    )


@router.get("/settings")
def settings_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    settings = db.query(SystemSettings).first()
    if not settings:
        settings = SystemSettings(email_enabled=True, target_email="admin@qrpass.local")
        db.add(settings)
        db.commit()
        db.refresh(settings)

    return templates.TemplateResponse(
        request,
        "settings.html",
        {"user": current_user, "settings": settings, "success_msg": request.query_params.get("success")},
    )


@router.post("/settings")
def save_settings(
    request: Request,
    email_enabled: str = Form(default="off"),
    target_email: str = Form(...),
    pc_inactive_alert_enabled: str = Form(default="off"),
    pc_inactive_threshold_hours: int = Form(default=24),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    settings = db.query(SystemSettings).first()
    if not settings:
        settings = SystemSettings()
        db.add(settings)

    settings.email_enabled = email_enabled == "on"
    settings.target_email = target_email
    settings.pc_inactive_alert_enabled = pc_inactive_alert_enabled == "on"
    settings.pc_inactive_threshold_hours = pc_inactive_threshold_hours
    db.commit()

    return RedirectResponse(url=app_url("/settings?success=1"), status_code=303)
