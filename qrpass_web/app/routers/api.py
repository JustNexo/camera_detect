import asyncio
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.camera_scope import scope_key
from app.core.config import settings
from app.core.database import get_db
from app.models import CameraPresence, PigCountEvent, SystemSettings, Violation
from app.services.email_service import send_violation_email
from app.state import camera_rules, camera_status, store_latest_frame, is_stream_requested

router = APIRouter(prefix="/api", tags=["api"])


last_db_write: dict[str, float] = {}


class HeartbeatItem(BaseModel):
    camera_name: str
    site_name: str = ""
    rule_summary: str = ""


class HeartbeatBatch(BaseModel):
    items: list[HeartbeatItem]

def _upsert_camera_presence(db: Session, key: str, rule_summary: str) -> None:
    """Обновление last_seen и (опционально) правила — одна БД для всех воркеров."""
    now = datetime.now(timezone.utc)
    now_ts = now.timestamp()
    
    # Троттлинг записи в БД (не чаще 1 раза в 15 секунд на воркер)
    last_write = last_db_write.get(key, 0.0)
    if (now_ts - last_write) < 15.0:
        return
    last_db_write[key] = now_ts

    try:
        row = db.query(CameraPresence).filter(CameraPresence.scope_key == key).first()
        rs = (rule_summary or "").strip()
        if row:
            row.last_seen = now
            if rs:
                row.rule_summary = rs
        else:
            db.add(
                CameraPresence(
                    scope_key=key,
                    last_seen=now,
                    rule_summary=rs or "Правило не передано",
                )
            )
        # commit делается снаружи (в heartbeat_batch) или одинарно (в heartbeat)
    except Exception as e:
        db.rollback()
        # Если база залочена, просто пропускаем эту запись, запишем в следующий раз
        print(f"Warning: Failed to update camera presence in DB: {e}")


def verify_api_token(x_api_token: str | None = Header(default=None)) -> None:
    if x_api_token != settings.client_api_token:
        raise HTTPException(status_code=401, detail="Неверный API токен")


def _safe_database_url(url: str) -> str:
    if url.startswith("sqlite"):
        return url
    if "@" in url and "://" in url:
        try:
            scheme, rest = url.split("://", 1)
            if "@" in rest:
                return f"{scheme}://***@{rest.split('@', 1)[1]}"
        except Exception:
            pass
    return url


@router.get("/_debug/selfcheck", include_in_schema=False)
def selfcheck(_: None = Depends(verify_api_token)):
    """Диагностика путей и прав записи на хостинге (только с X-API-Token)."""
    import sys

    project_root = Path(__file__).resolve().parent.parent.parent
    write_tests: dict[str, object] = {}
    for label, path in (
        ("tmp", Path("/tmp/qrpass_selfcheck.txt")),
        ("project", project_root / "qrpass_selfcheck.txt"),
        ("home", Path.home() / "qrpass_selfcheck.txt"),
    ):
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("ok", encoding="utf-8")
            write_tests[label] = {"path": str(path), "ok": True}
        except OSError as e:
            write_tests[label] = {"path": str(path), "ok": False, "err": str(e)}

    itsdangerous_ok = False
    try:
        import itsdangerous  # noqa: F401

        itsdangerous_ok = True
    except ImportError:
        pass

    from app.core import security as security_mod

    import bcrypt as bcrypt_mod

    long_password_test: dict[str, object] = {"backend": "bcrypt_native", "module_file": security_mod.__file__}
    try:
        h = security_mod.get_password_hash("x" * 200)
        ok = security_mod.verify_password("x" * 200, h)
        long_password_test["hash_long_password_ok"] = bool(ok)
        long_password_test["bcrypt_version"] = getattr(bcrypt_mod, "__version__", "?")
    except Exception as exc:
        long_password_test["error"] = repr(exc)

    return {
        "project_root": str(project_root),
        "cwd": str(Path.cwd()),
        "python": sys.version,
        "root_path": settings.root_path,
        "error_log_dir": getattr(settings, "error_log_dir", "") or "",
        "database_url": _safe_database_url(settings.database_url),
        "write_tests": write_tests,
        "itsdangerous": itsdangerous_ok,
        "password_security": long_password_test,
    }


@router.post("/heartbeat", dependencies=[Depends(verify_api_token)])
def heartbeat(
    camera_name: str = Form(...),
    site_name: str = Form(""),
    rule_summary: str = Form(""),
    db: Session = Depends(get_db),
):
    key = scope_key(site_name, camera_name)
    camera_status[key] = datetime.now(timezone.utc)
    if (rule_summary or "").strip():
        camera_rules[key] = rule_summary.strip()
    _upsert_camera_presence(db, key, rule_summary)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Warning: Failed to update camera presence in DB: {e}")

    stream_requested = is_stream_requested(key)

    return {
        "ok": True,
        "camera_name": camera_name,
        "site_name": site_name,
        "scope_key": key,
        "stream_requested": stream_requested,
    }


@router.post("/heartbeat_batch", dependencies=[Depends(verify_api_token)])
def heartbeat_batch(payload: HeartbeatBatch, db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    out: list[dict[str, object]] = []
    # Одно DB-commit на весь батч (резко меньше блокировок/процессов).
    for it in payload.items[:500]:
        cam = (it.camera_name or "").strip()
        if not cam:
            continue
        site = (it.site_name or "").strip()
        rs = (it.rule_summary or "").strip()
        key = scope_key(site, cam)
        camera_status[key] = now
        if rs:
            camera_rules[key] = rs
        _upsert_camera_presence(db, key, rs)
        out.append(
            {
                "camera_name": cam,
                "site_name": site,
                "scope_key": key,
                "stream_requested": bool(is_stream_requested(key)),
            }
        )
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Warning: Failed to update camera presence in DB: {e}")
    return {"ok": True, "count": len(out), "items": out}


@router.post("/stream_frame", dependencies=[Depends(verify_api_token)])
async def stream_frame(
    camera_name: str = Form(...),
    frame: UploadFile = File(...),
    site_name: str = Form(""),
    rule_summary: str = Form(""),
    db: Session = Depends(get_db),
):
    data = await frame.read()
    key = scope_key(site_name, camera_name)
    store_latest_frame(key, data)
    camera_status[key] = datetime.now(timezone.utc)
    if (rule_summary or "").strip():
        camera_rules[key] = rule_summary.strip()
    _upsert_camera_presence(db, key, rule_summary)
    return {"ok": True, "camera_name": camera_name, "site_name": site_name, "scope_key": key}


@router.post("/violation", dependencies=[Depends(verify_api_token)])
async def violation(
    camera_name: str = Form(...),
    violation_type: str = Form(...),
    image: UploadFile = File(...),
    site_name: str = Form(""),
    db: Session = Depends(get_db),
):
    output_dir = Path("static/violations")
    output_dir.mkdir(parents=True, exist_ok=True)

    suffix = Path(image.filename or "violation.jpg").suffix or ".jpg"
    file_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}{suffix}"
    file_path = output_dir / file_name

    content = await image.read()
    max_v = max(256 * 1024, int(getattr(settings, "violation_upload_max_bytes", 6 * 1024 * 1024)))
    if len(content) > max_v:
        raise HTTPException(status_code=413, detail="Слишком большой файл")
    with file_path.open("wb") as file:
        file.write(content)

    db_violation = Violation(
        site_name=(site_name or "").strip(),
        camera_name=camera_name,
        violation_type=violation_type,
        image_path=f"/static/violations/{file_name}",
    )
    db.add(db_violation)
    db.commit()
    db.refresh(db_violation)

    sys_settings = db.query(SystemSettings).first()
    email_enabled = sys_settings.email_enabled if sys_settings else False
    target_email = sys_settings.target_email if sys_settings else ""

    timestamp = db_violation.timestamp.strftime("%Y-%m-%d %H:%M:%S")
    asyncio.create_task(
        asyncio.to_thread(
            send_violation_email,
            camera_name=camera_name,
            violation_type=violation_type,
            timestamp=timestamp,
            image_path=str(file_path),
            email_enabled=email_enabled,
            target_email=target_email,
            site_name=db_violation.site_name or "",
        )
    )
    return {"ok": True, "id": db_violation.id}


@router.post("/pig_count", dependencies=[Depends(verify_api_token)])
async def pig_count(
    camera_name: str = Form(...),
    count: int = Form(...),
    ts_from: float = Form(...),
    ts_to: float = Form(...),
    site_name: str = Form(""),
    direction: str = Form("up"),
    line_y_ratio: float = Form(0.58),
    preview: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    c = int(count or 0)
    if c <= 0:
        raise HTTPException(status_code=400, detail="count должен быть > 0")
    output_dir = Path("static/pig_count")
    output_dir.mkdir(parents=True, exist_ok=True)
    preview_path = ""
    if preview is not None:
        content = await preview.read()
        max_v = max(256 * 1024, int(getattr(settings, "violation_upload_max_bytes", 6 * 1024 * 1024)))
        if len(content) > max_v:
            raise HTTPException(status_code=413, detail="Слишком большой файл")
        suffix = Path(preview.filename or "pig_preview.jpg").suffix or ".jpg"
        file_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}{suffix}"
        file_path = output_dir / file_name
        with file_path.open("wb") as f:
            f.write(content)
        preview_path = f"/static/pig_count/{file_name}"

    dt_from = datetime.fromtimestamp(float(ts_from), tz=timezone.utc)
    dt_to = datetime.fromtimestamp(float(ts_to), tz=timezone.utc)
    event = PigCountEvent(
        site_name=(site_name or "").strip(),
        camera_name=camera_name,
        direction=(direction or "up").strip() or "up",
        line_y_ratio=float(line_y_ratio),
        count=c,
        ts_from=dt_from,
        ts_to=dt_to,
        preview_path=preview_path,
        created_at=datetime.now(timezone.utc),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return {"ok": True, "id": event.id}
