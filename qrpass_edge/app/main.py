from __future__ import annotations

import asyncio
import logging
from logging.handlers import RotatingFileHandler
import os
import sqlite3
import threading
import hashlib
import subprocess
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Body
from fastapi.responses import FileResponse, HTMLResponse, Response

from app import cameras_db, queue_db
from app.agent_loop import agent_thread_body
from app.config import settings
from app.hashfile import sha256_file
from app.storage_gc import run_storage_gc
from app.uploader import ping_selfcheck, post_heartbeat, post_stream_frame, post_heartbeat_batch

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
_log = logging.getLogger(__name__)

# Файловый лог (ротация): ошибки/запуски/остановки/операции.
try:
    settings.log_file_path.parent.mkdir(parents=True, exist_ok=True)
    fh = RotatingFileHandler(
        str(settings.log_file_path),
        maxBytes=max(1, int(settings.log_max_mb)) * 1024 * 1024,
        backupCount=max(1, int(settings.log_backups)),
        encoding="utf-8",
    )
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.getLogger().addHandler(fh)
except Exception as e:
    _log.warning("Не удалось инициализировать файловый лог: %s", e)

_conn: sqlite3.Connection | None = None
_agent_stop: threading.Event | None = None
_agent_thread: threading.Thread | None = None


def _preview_dir() -> Path:
    p = settings.storage_root / "_previews"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _preview_path(camera_name: str) -> Path:
    key = hashlib.md5((camera_name or "").strip().encode("utf-8")).hexdigest()
    return _preview_dir() / f"{key}.jpg"


def _store_preview(camera_name: str, data: bytes) -> None:
    if not camera_name:
        return
    try:
        _preview_path(camera_name).write_bytes(data)
    except OSError:
        pass


def _pig_preview_dir() -> Path:
    p = settings.storage_root / "_pig_previews"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        raise RuntimeError("БД не инициализирована")
    return _conn


def _tail_text_file(path: Path, max_lines: int = 200) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"Ошибка чтения лога: {e}"
    lines = text.splitlines()
    return "\n".join(lines[-max_lines:])


def _storage_root() -> Path:
    return settings.storage_root.resolve()


def _iter_storage_files(root: Path) -> Iterable[Path]:
    if not root.exists():
        return []
    out: list[Path] = []
    for p in root.rglob("*"):
        if p.is_file():
            out.append(p)
    out.sort(key=lambda x: x.stat().st_mtime if x.exists() else 0.0, reverse=True)
    return out


def _safe_rel_to_root(root: Path, rel: str) -> Path:
    p = (root / rel).resolve()
    root_str = str(root)
    p_str = str(p)
    if not (p_str == root_str or p_str.startswith(root_str + os.sep)):
        raise HTTPException(status_code=400, detail="Недопустимый путь")
    return p


def _service_name() -> str:
    return settings.client_service_name or "qrpass-client.service"


def _run_systemctl(*args: str) -> tuple[int, str]:
    try:
        cp = subprocess.run(
            ["systemctl", *args],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
        out = (cp.stdout or cp.stderr or "").strip()
        return int(cp.returncode), out
    except Exception as e:
        return 1, str(e)


def _run_pgrep(pattern: str) -> tuple[bool, str]:
    try:
        cp = subprocess.run(
            ["pgrep", "-fa", pattern],
            capture_output=True,
            text=True,
            timeout=4,
            check=False,
        )
        out = (cp.stdout or "").strip()
        return (cp.returncode == 0 and bool(out)), out
    except Exception as e:
        return False, str(e)


def _have_cmd(name: str) -> bool:
    return subprocess.run(["which", name], capture_output=True, text=True, check=False).returncode == 0


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _conn, _agent_stop, _agent_thread
    settings.storage_root.mkdir(parents=True, exist_ok=True)
    _conn = queue_db.connect(settings.queue_db_path)
    queue_db.init_schema(_conn)
    cameras_db.init_schema(_conn)
    # Настройки, меняемые из UI (2.2): папка хранения.
    saved_root = queue_db.get_setting(_conn, "storage_root", "")
    if saved_root.strip():
        settings.storage_root = Path(saved_root.strip())
    _agent_stop = threading.Event()
    _agent_thread = threading.Thread(
        target=agent_thread_body,
        args=(_agent_stop, _conn),
        name="qrpass-edge-agent",
        daemon=True,
    )
    _agent_thread.start()
    _log.info(
        "QRPass Edge UI %s:%s, queue=%s, storage=%s",
        settings.edge_ui_host,
        settings.edge_ui_port,
        settings.queue_db_path,
        settings.storage_root,
    )
    yield
    if _agent_stop:
        _agent_stop.set()
    if _agent_thread:
        _agent_thread.join(timeout=10.0)
    if _conn:
        _conn.close()
        _conn = None


app = FastAPI(title="QRPass Edge", lifespan=lifespan)


@app.get("/health")
def health():
    return {"ok": True, "service": "qrpass-edge"}


@app.get("/api/queue/stats")
def api_queue_stats():
    return queue_db.stats(_get_conn())


@app.get("/api/queue/recent")
def api_queue_recent(limit: int = 40):
    lim = max(5, min(200, limit))
    return queue_db.recent_events(_get_conn(), lim)


@app.get("/api/events")
def api_events(
    limit: int = 100,
    camera_name: str = "",
    violation_type: str = "",
    date_from: str = "",
    date_to: str = "",
):
    lim = max(10, min(500, int(limit)))
    ts_from: float | None = None
    ts_to: float | None = None
    try:
        if date_from.strip():
            ts_from = datetime.strptime(date_from.strip(), "%Y-%m-%d").timestamp()
        if date_to.strip():
            d = datetime.strptime(date_to.strip(), "%Y-%m-%d") + timedelta(days=1) - timedelta(seconds=1)
            ts_to = d.timestamp()
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат даты, нужен YYYY-MM-DD")
    return queue_db.filtered_events(
        _get_conn(),
        limit=lim,
        camera_name=camera_name,
        violation_type=violation_type,
        created_from_ts=ts_from,
        created_to_ts=ts_to,
    )


@app.post("/api/queue/run_gc")
def api_run_gc():
    return run_storage_gc(_get_conn())


@app.get("/api/storage/config")
def api_storage_config():
    return {
        "storage_root": str(settings.storage_root),
        "storage_max_gb": float(settings.storage_max_gb or 0.0),
    }


@app.post("/api/storage/config")
def api_storage_config_set(storage_root: str = Form(...)):
    root = Path((storage_root or "").strip()).expanduser()
    if not root.is_absolute():
        raise HTTPException(status_code=400, detail="Укажите абсолютный путь")
    try:
        root.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Не удалось создать/использовать путь: {e}")
    settings.storage_root = root
    queue_db.set_setting(_get_conn(), "storage_root", str(root))
    return {"ok": True, "storage_root": str(root)}


@app.post("/api/ping")
def api_ping():
    if not settings.upstream_enabled:
        return {"ok": True, "http_code": None, "message": "UPSTREAM_ENABLED=false (локальный режим)"}
    r = ping_selfcheck()
    return {"ok": r.ok, "http_code": r.http_code, "message": r.message[:500]}


@app.get("/api/service/status")
def api_service_status():
    svc = _service_name()
    rc, out = _run_systemctl("is-active", svc)
    active = (out.strip() == "active")
    mode = "systemd"
    proc_lines = ""
    if not active:
        ok_proc, proc_out = _run_pgrep(settings.client_process_pattern or "qrpass_client/main.py")
        if ok_proc:
            active = True
            mode = "manual"
            proc_lines = proc_out
    return {
        "ok": active,
        "service": svc,
        "active": active,
        "state": out,
        "mode": mode,
        "process": proc_lines[:400],
    }


@app.post("/api/service/action")
def api_service_action(action: str = Form(...)):
    act = (action or "").strip().lower()
    if act not in {"start", "stop", "restart"}:
        raise HTTPException(status_code=400, detail="Недопустимое действие")
    svc = _service_name()
    rc, out = _run_systemctl(act, svc)
    ok = rc == 0
    return {"ok": ok, "service": svc, "action": act, "message": out[:400]}


@app.post("/api/storage/open")
def api_storage_open():
    root = settings.storage_root
    root.mkdir(parents=True, exist_ok=True)
    # Для kiosk-сценария на Linux: открыть папку в файловом менеджере.
    if os.name != "posix":
        return {"ok": False, "message": "Открытие папки поддерживается только на Linux"}
    display = os.getenv("DISPLAY", "").strip()
    if not display:
        return {"ok": False, "message": f"Нет GUI-сессии (DISPLAY не задан). Папка: {root}"}
    candidates: list[list[str]] = []
    if _have_cmd("xdg-open"):
        candidates.append(["xdg-open", str(root)])
        candidates.append(["xdg-open", f"file://{root}"])
    if _have_cmd("gio"):
        candidates.append(["gio", "open", str(root)])
    for fm in ("nautilus", "thunar", "pcmanfm", "dolphin", "nemo"):
        if _have_cmd(fm):
            candidates.append([fm, str(root)])
    last_err = "Не найден подходящий файловый менеджер"
    for cmd in candidates:
        try:
            cp = subprocess.run(cmd, capture_output=True, text=True, timeout=6, check=False)
            if cp.returncode == 0:
                return {"ok": True, "message": str(root)}
            out = (cp.stdout or cp.stderr or "").strip()
            if out:
                last_err = out.splitlines()[-1]
        except Exception as e:
            last_err = str(e)
    return {"ok": False, "message": f"{last_err[:200]} | Папка: {root}"}


@app.get("/api/storage/files")
def api_storage_files(limit: int = 300):
    lim = max(20, min(2000, int(limit)))
    root = _storage_root()
    rows: list[dict[str, object]] = []
    for p in _iter_storage_files(root):
        try:
            st = p.stat()
        except OSError:
            continue
        rows.append(
            {
                "name": p.name,
                "rel_path": str(p.relative_to(root)).replace("\\\\", "/"),
                "size": int(st.st_size),
                "mtime": float(st.st_mtime),
            }
        )
        if len(rows) >= lim:
            break
    return {"ok": True, "root": str(root), "files": rows}


@app.get("/api/storage/file")
def api_storage_file(rel_path: str):
    root = _storage_root()
    p = _safe_rel_to_root(root, rel_path)
    if not p.is_file():
        raise HTTPException(status_code=404, detail="Файл не найден")
    return FileResponse(path=str(p), filename=p.name)


@app.get("/api/logs/recent")
def api_logs_recent(lines: int = 200):
    n = max(20, min(2000, int(lines)))
    text = _tail_text_file(settings.log_file_path, n)
    return {"ok": True, "path": str(settings.log_file_path), "text": text}


@app.post("/api/local/heartbeat")
def api_local_heartbeat(
    camera_name: str | None = None,
    rule_summary: str = "",
    camera_address: str = "",
    checks_csv: str = "",
):
    cam = (camera_name or settings.default_camera_name).strip()
    checks = [x.strip() for x in checks_csv.split(",") if x.strip()]
    if not settings.upstream_enabled:
        cameras_db.touch_camera_seen_with_meta(
            _get_conn(),
            camera_name=cam,
            err="",
            address=camera_address,
            checks=checks,
        )
        return {"ok": True, "http_code": None, "message": "saved local (upstream disabled)"}
    r = post_heartbeat(
        camera_name=cam,
        site_name=settings.site_name,
        rule_summary=rule_summary,
    )
    cameras_db.touch_camera_seen_with_meta(
        _get_conn(),
        camera_name=cam,
        err="" if r.ok else r.message,
        address=camera_address,
        checks=checks,
    )
    return {"ok": r.ok, "http_code": r.http_code, "message": r.message[:500]}


@app.post("/api/local/heartbeat_batch")
async def api_local_heartbeat_batch(payload: dict = Body(...)):
    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        raise HTTPException(status_code=400, detail="items must be list")

    out_items: list[dict] = []
    for it in items[:500]:
        if not isinstance(it, dict):
            continue
        cam = str(it.get("camera_name") or "").strip()
        if not cam:
            continue
        rule_summary = str(it.get("rule_summary") or "")
        camera_address = str(it.get("camera_address") or "")
        checks_csv = str(it.get("checks_csv") or "")
        checks = [x.strip() for x in checks_csv.split(",") if x.strip()]
        cameras_db.touch_camera_seen_with_meta(
            _get_conn(),
            camera_name=cam,
            err="",
            address=camera_address,
            checks=checks,
        )
        out_items.append(
            {
                "camera_name": cam,
                "site_name": settings.site_name,
                "rule_summary": rule_summary,
            }
        )

    if not settings.upstream_enabled:
        return {"ok": True, "count": len(out_items), "message": "saved local (upstream disabled)"}

    # Отправляем на сайт одним запросом (батч).
    r = await asyncio.to_thread(post_heartbeat_batch, items=out_items, timeout=10.0)
    return {"ok": r.ok, "http_code": r.http_code, "message": r.message[:500], "count": len(out_items)}


@app.get("/api/cameras")
def api_cameras_list():
    return cameras_db.list_cameras(_get_conn())


@app.post("/api/cameras")
def api_cameras_create(
    name: str = Form(...),
    address: str = Form(""),
    username: str = Form(""),
    password: str = Form(""),
    checks_csv: str = Form(""),
    enabled: int = Form(1),
):
    checks = [x.strip() for x in checks_csv.split(",") if x.strip()]
    try:
        row = cameras_db.upsert_camera(
            _get_conn(),
            camera_id=None,
            name=name,
            address=address,
            username=username,
            password=password,
            checks=checks,
            enabled=bool(enabled),
        )
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Камера с таким именем уже существует")
    return {"ok": True, "camera": row}


@app.post("/api/cameras/{camera_id}")
def api_cameras_update(
    camera_id: int,
    name: str = Form(...),
    address: str = Form(""),
    username: str = Form(""),
    password: str = Form(""),
    checks_csv: str = Form(""),
    enabled: int = Form(1),
):
    checks = [x.strip() for x in checks_csv.split(",") if x.strip()]
    try:
        row = cameras_db.upsert_camera(
            _get_conn(),
            camera_id=camera_id,
            name=name,
            address=address,
            username=username,
            password=password,
            checks=checks,
            enabled=bool(enabled),
        )
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Камера с таким именем уже существует")
    return {"ok": True, "camera": row}


@app.delete("/api/cameras/{camera_id}")
def api_cameras_delete(camera_id: int):
    ok = cameras_db.delete_camera(_get_conn(), camera_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Камера не найдена")
    return {"ok": True}


@app.post("/api/cameras/reset_legacy_checks")
def api_cameras_reset_legacy_checks():
    n = cameras_db.reset_legacy_perimeter_checks(_get_conn())
    return {"ok": True, "updated": n}


@app.post("/api/cameras/{camera_id}/clear_checks")
def api_cameras_clear_checks(camera_id: int):
    ok = cameras_db.clear_camera_checks(_get_conn(), camera_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Камера не найдена")
    return {"ok": True}


@app.get("/api/cameras/{camera_id}/preview")
def api_camera_preview(camera_id: int):
    cam = cameras_db.get_camera(_get_conn(), camera_id)
    if not cam:
        raise HTTPException(status_code=404, detail="Камера не найдена")
    p = _preview_path(str(cam.get("name") or ""))
    if not p.is_file():
        raise HTTPException(status_code=404, detail="Кадр пока недоступен")
    try:
        data = p.read_bytes()
    except OSError:
        raise HTTPException(status_code=404, detail="Кадр пока недоступен")
    return Response(
        content=data,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate, max-age=0"},
    )


@app.post("/api/local/stream_frame")
async def api_local_stream_frame(
    frame: UploadFile = File(...),
    camera_name: str | None = Form(None),
    rule_summary: str = Form(""),
    camera_address: str = Form(""),
    checks_csv: str = Form(""),
):
    cam = (camera_name or settings.default_camera_name).strip()
    checks = [x.strip() for x in checks_csv.split(",") if x.strip()]
    root = settings.storage_root
    root.mkdir(parents=True, exist_ok=True)
    suffix = Path(frame.filename or "frame.jpg").suffix or ".jpg"
    tmp = root / f"preview_{int(time.time() * 1000)}{suffix}"
    data = await frame.read()
    if len(data) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Файл слишком большой")
    _store_preview(cam, data)
    tmp.write_bytes(data)
    try:
        if not settings.upstream_enabled:
            cameras_db.touch_camera_seen_with_meta(
                _get_conn(),
                camera_name=cam,
                err="",
                address=camera_address,
                checks=checks,
            )
            ok = True
            http_code = None
            message = "saved local (upstream disabled)"
        elif not settings.upstream_stream_enabled:
            # Отдельный режим: heartbeat/violations отправляем, видеопоток на сайт не шлём.
            cameras_db.touch_camera_seen_with_meta(
                _get_conn(),
                camera_name=cam,
                err="",
                address=camera_address,
                checks=checks,
            )
            ok = True
            http_code = None
            message = "saved local (stream uplink disabled)"
        else:
            # Важно: requests.post внутри post_stream_frame блокирующий.
            # Уносим в thread, чтобы event loop FastAPI не подвисал при сети/сервере.
            r = await asyncio.to_thread(
                post_stream_frame,
                frame_path=tmp,
                camera_name=cam,
                site_name=settings.site_name,
                rule_summary=rule_summary,
                timeout=3.0,
            )
            cameras_db.touch_camera_seen_with_meta(
                _get_conn(),
                camera_name=cam,
                err="" if r.ok else r.message,
                address=camera_address,
                checks=checks,
            )
            ok = r.ok
            http_code = r.http_code
            message = r.message
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
    return {"ok": ok, "http_code": http_code, "message": str(message)[:500]}


@app.post("/api/local/enqueue")
async def api_local_enqueue(
    camera_name: str = Form(...),
    violation_type: str = Form(...),
    image: UploadFile = File(...),
):
    """Сохранить снимок в STORAGE_ROOT и поставить в очередь (демо / интеграционный тест)."""
    root = settings.storage_root
    root.mkdir(parents=True, exist_ok=True)
    suffix = Path(image.filename or "shot.jpg").suffix or ".jpg"
    dest = root / f"local_{int(__import__('time').time() * 1000)}{suffix}"
    data = await image.read()
    if len(data) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Файл слишком большой")
    dest.write_bytes(data)
    digest = sha256_file(dest)
    inserted = queue_db.enqueue_violation(
        _get_conn(),
        camera_name=camera_name.strip(),
        violation_type=violation_type.strip(),
        file_path=dest,
        file_sha256=digest,
    )
    return {"ok": True, "path": str(dest), "enqueued": inserted}


@app.post("/api/local/pig_count_event")
async def api_local_pig_count_event(
    camera_name: str = Form(...),
    count: int = Form(...),
    ts_from: float = Form(...),
    ts_to: float = Form(...),
    direction: str = Form("up"),
    line_y_ratio: float = Form(0.58),
    preview: UploadFile | None = File(None),
):
    cam = (camera_name or "").strip()
    if not cam:
        raise HTTPException(status_code=400, detail="camera_name обязателен")
    n = int(count or 0)
    if n <= 0:
        raise HTTPException(status_code=400, detail="count должен быть > 0")

    preview_path: Path | None = None
    if preview is not None:
        data = await preview.read()
        if data:
            if len(data) > 20 * 1024 * 1024:
                raise HTTPException(status_code=413, detail="preview слишком большой")
            suffix = Path(preview.filename or "pig.jpg").suffix or ".jpg"
            preview_path = _pig_preview_dir() / f"pig_{int(time.time() * 1000)}{suffix}"
            preview_path.write_bytes(data)

    dedup_raw = f"{cam}|{n}|{float(ts_from):.3f}|{float(ts_to):.3f}|{direction}|{float(line_y_ratio):.3f}|{int(time.time())}"
    event_sha = hashlib.sha256(dedup_raw.encode("utf-8")).hexdigest()
    inserted = queue_db.enqueue_pig_count(
        _get_conn(),
        camera_name=cam,
        count=n,
        ts_from=float(ts_from),
        ts_to=float(ts_to),
        direction=(direction or "up"),
        line_y_ratio=float(line_y_ratio),
        file_path=preview_path,
        event_sha256=event_sha,
    )
    if settings.upstream_enabled and not inserted:
        # При случайном dedup не считаем это ошибкой.
        return {"ok": True, "enqueued": False}
    return {"ok": True, "enqueued": inserted}


@app.get("/", response_class=HTMLResponse)
def ui_home():
    return """<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>QRPass Edge</title>
  <style>
    :root {
      --bg: #e9eef3;
      --panel: #ffffff;
      --text: #1f2a37;
      --muted: #5f6b7a;
      --line: #d7dee6;
      --primary: #0f5cc0;
      --primary-hi: #0d4fa6;
      --warn: #c62828;
      --ok: #2e7d32;
      --radius: 12px;
      --shadow: 0 2px 10px rgba(16,24,40,.06);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      font-family: "Segoe UI", Inter, system-ui, sans-serif;
      background: linear-gradient(180deg, #dde5ee 0, #e9eef3 240px);
      color: var(--text);
      line-height: 1.45;
      font-size: 15px;
    }
    .wrap { max-width: 1180px; margin: 0 auto; padding: 1.2rem 1rem 2rem; }
    header {
      margin-bottom: 1rem;
      background: #0f1722;
      color: #f7f9fc;
      border-radius: var(--radius);
      padding: 1rem 1.1rem;
      box-shadow: var(--shadow);
    }
    header h1 { font-size: 1.15rem; font-weight: 700; margin: 0 0 .2rem; letter-spacing: .01em; }
    header p { margin: 0; color: #c8d2df; font-size: .89rem; max-width: 74rem; }
    header a { color: #a8c8ff; }
    .layout {
      display: grid;
      grid-template-columns: 2fr 1fr;
      gap: 1rem;
      align-items: start;
    }
    .card {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      padding: 1rem 1.1rem;
      margin-bottom: 1rem;
    }
    .card h2 {
      font-size: .9rem;
      text-transform: uppercase;
      letter-spacing: .06em;
      color: var(--muted);
      margin: 0 0 .75rem;
      font-weight: 700;
    }
    .actions { display: flex; flex-wrap: wrap; gap: .5rem; margin-bottom: .75rem; }
    button.btn {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: .48rem .9rem;
      font-size: .88rem;
      font-weight: 600;
      cursor: pointer; transition: background .15s, opacity .15s;
    }
    button.btn:disabled { opacity: .55; cursor: not-allowed; }
    button.btn-primary { background: var(--primary); color: #fff; border-color: var(--primary); }
    button.btn-primary:hover:not(:disabled) { background: var(--primary-hi); }
    button.btn-secondary { background: #f8fafc; color: var(--text); }
    button.btn-secondary:hover:not(:disabled) { background: #f1f5f9; }
    button.btn-danger { background: #fff; color: var(--warn); border: 1px solid #ffcdd2; }
    button.btn-danger:hover:not(:disabled) { background: #fff5f5; }
    .chips { display: flex; flex-wrap: wrap; gap: .5rem; margin-top: .5rem; }
    .chip {
      display: inline-flex; align-items: center; gap: .35rem; padding: .25rem .6rem;
      border-radius: 999px; font-size: .82rem; font-weight: 600; background: #eef3f8; color: var(--muted);
    }
    .chip b { color: var(--text); font-weight: 650; }
    .msg { font-size: .88rem; color: var(--muted); min-height: 1.2em; margin-top: .5rem; }
    .msg.err { color: var(--warn); }
    .msg.ok { color: var(--ok); }
    table { width: 100%; border-collapse: collapse; font-size: .84rem; }
    th, td { text-align: left; padding: .5rem .45rem; border-bottom: 1px solid var(--line); vertical-align: top; }
    th { color: var(--muted); font-weight: 600; font-size: .78rem; text-transform: uppercase; letter-spacing: .03em; }
    tr:last-child td { border-bottom: none; }
    .st-pending { color: #e65100; font-weight: 600; }
    .st-sending { color: #1565c0; font-weight: 600; }
    .st-sent { color: var(--ok); font-weight: 600; }
    .st-fail, .st-skipped { color: var(--danger); font-weight: 600; }
    .mono { font-family: ui-monospace, monospace; font-size: .78rem; word-break: break-all; }
    form .field { margin-bottom: .75rem; }
    form label { display: block; font-size: .82rem; font-weight: 600; color: var(--muted); margin-bottom: .25rem; }
    form input[type="text"], form input[type="file"] { width: 100%; max-width: 28rem; }
    form input[type="text"] {
      padding: .5rem .65rem; border: 1px solid var(--line); border-radius: 8px; font-size: .95rem;
    }
    .scroll { overflow-x: auto; -webkit-overflow-scrolling: touch; }
    pre.raw {
      margin: .75rem 0 0; padding: .75rem; background: #192231; color: #e2e8f0; border-radius: 8px;
      font-size: .78rem; overflow: auto; max-height: 14rem;
    }
    .side .card { position: sticky; top: 1rem; }
    @media (max-width: 980px) {
      .layout { grid-template-columns: 1fr; }
      .side .card { position: static; }
    }
  </style>
</head>
<body>
  <div class="wrap">
    <header>
      <h1>QRPass Edge</h1>
      <p>Локальная панель мини‑ПК: очередь отправки на основной сайт, проверка связи и тестовая загрузка.
         Данные нарушений уходят на сервер из настроек (<code>SERVER_URL</code>), не на эту страницу.
         <a href="/cameras">Настройка камер</a> • <a href="/events">Журнал сработок</a> • <a href="/files">Файлы</a> • <a href="/logs">Логи</a>.</p>
    </header>

    <div class="layout">
      <div class="main">
        <section class="card">
          <h2>Состояние</h2>
          <div class="actions">
            <button type="button" class="btn btn-primary" id="btnStats">Обновить</button>
            <button type="button" class="btn btn-secondary" id="btnPing">Проверка связи</button>
            <button type="button" class="btn btn-danger" id="btnGc">Очистка диска</button>
            <button type="button" class="btn btn-secondary" id="btnServiceStatus">Статус сервиса</button>
            <button type="button" class="btn btn-secondary" id="btnServiceStart">Старт сервиса</button>
            <button type="button" class="btn btn-secondary" id="btnServiceStop">Стоп сервиса</button>
            <button type="button" class="btn btn-secondary" id="btnServiceRestart">Рестарт сервиса</button>
            <button type="button" class="btn btn-secondary" id="btnOpenFolder">Открыть папку</button>
          </div>
      <div class="field">
        <label for="storageRoot">Папка хранения файлов нарушений</label>
        <div style="display:flex; gap:.5rem; flex-wrap:wrap;">
          <input type="text" id="storageRoot" style="min-width:420px; max-width:760px; width:100%;"/>
          <button type="button" class="btn btn-secondary" id="btnSaveStorageRoot">Сохранить путь</button>
        </div>
      </div>
          <div class="chips" id="chips"></div>
          <p class="msg" id="statusMsg"></p>
          <div class="scroll" id="tableWrap" style="display:none;margin-top:.75rem;">
            <table>
              <thead><tr><th>ID</th><th>Время</th><th>Камера</th><th>Тип</th><th>Статус</th></tr></thead>
              <tbody id="tbody"></tbody>
            </table>
          </div>
          <pre class="raw" id="rawExtra" style="display:none;"></pre>
        </section>
      </div>

      <div class="side">
        <section class="card">
          <h2>В очередь (тест)</h2>
          <form id="f">
            <div class="field">
              <label for="cam">Камера</label>
              <input type="text" id="cam" name="camera_name" value="TEST-CAM-1" autocomplete="off"/>
            </div>
            <div class="field">
              <label for="vtype">Тип нарушения</label>
              <input type="text" id="vtype" name="violation_type" value="Тест edge" autocomplete="off"/>
            </div>
            <div class="field">
              <label for="img">Файл изображения</label>
              <input id="img" name="image" type="file" accept="image/*"/>
            </div>
            <button type="submit" class="btn btn-primary" id="btnSubmit">Добавить в очередь</button>
          </form>
          <p class="msg" id="formMsg"></p>
        </section>
      </div>
    </div>
  </div>
  <script>
  const chips = document.getElementById('chips');
  const statusMsg = document.getElementById('statusMsg');
  const tbody = document.getElementById('tbody');
  const tableWrap = document.getElementById('tableWrap');
  const rawExtra = document.getElementById('rawExtra');
  const formMsg = document.getElementById('formMsg');
  const storageRootInput = document.getElementById('storageRoot');

  function setBusy(btn, on) { if (btn) { btn.disabled = on; } }

  async function fetchJson(url, opt) {
    const r = await fetch(url, Object.assign({ headers: { 'Accept': 'application/json' } }, opt || {}));
    const t = await r.text();
    let data;
    try { data = JSON.parse(t); } catch (e) { data = { _raw: t }; }
    if (!r.ok) throw new Error((data && data.detail) || t || r.statusText);
    return data;
  }

  function fmtTime(ts) {
    if (ts == null) return '—';
    const d = new Date((typeof ts === 'number' && ts < 1e12 ? ts * 1000 : Number(ts)));
    return isNaN(d) ? String(ts) : d.toLocaleString('ru-RU');
  }

  function statClass(s) {
    const x = (s || '').toLowerCase();
    if (x === 'pending') return 'st-pending';
    if (x === 'sending') return 'st-sending';
    if (x === 'sent') return 'st-sent';
    if (x.indexOf('skip') >= 0) return 'st-skipped';
    return 'st-fail';
  }

  function renderChips(stats) {
    chips.innerHTML = '';
    const order = ['pending', 'sending', 'sent', 'skipped_no_file'];
    const labels = { pending: 'В очереди', sending: 'Отправка', sent: 'Отправлено', skipped_no_file: 'Пропуск' };
    for (const k of order) {
      if (stats[k] == null) continue;
      const el = document.createElement('span');
      el.className = 'chip';
      el.innerHTML = (labels[k] || k) + ': <b>' + stats[k] + '</b>';
      chips.appendChild(el);
    }
    if (stats.total != null) {
      const el = document.createElement('span');
      el.className = 'chip';
      el.innerHTML = 'Всего записей: <b>' + stats.total + '</b>';
      chips.appendChild(el);
    }
  }

  function renderTable(rows) {
    tbody.innerHTML = '';
    (rows || []).forEach(function (row) {
      const tr = document.createElement('tr');
      const st = row.status || '';
      tr.innerHTML =
        '<td class="mono">' + row.id + '</td>' +
        '<td>' + fmtTime(row.created_at) + '</td>' +
        '<td>' + (row.camera_name || '').replace(/</g, '&lt;') + '</td>' +
        '<td>' + (row.violation_type || '').replace(/</g, '&lt;') + '</td>' +
        '<td class="' + statClass(st) + '">' + st + '</td>';
      tbody.appendChild(tr);
    });
    tableWrap.style.display = rows && rows.length ? 'block' : 'none';
  }

  document.getElementById('btnStats').onclick = async function () {
    const btn = this;
    setBusy(btn, true);
    statusMsg.textContent = '';
    statusMsg.className = 'msg';
    rawExtra.style.display = 'none';
    try {
      const stats = await fetchJson('/api/queue/stats');
      const recent = await fetchJson('/api/queue/recent?limit=20');
      renderChips(stats);
      renderTable(recent);
      statusMsg.textContent = 'Данные обновлены.';
      statusMsg.className = 'msg ok';
    } catch (e) {
      statusMsg.textContent = String(e.message || e);
      statusMsg.className = 'msg err';
    }
    setBusy(btn, false);
  };

  document.getElementById('btnPing').onclick = async function () {
    const btn = this;
    setBusy(btn, true);
    statusMsg.textContent = '';
    statusMsg.className = 'msg';
    rawExtra.style.display = 'none';
    try {
      const data = await fetchJson('/api/ping', { method: 'POST' });
      statusMsg.textContent = data.ok ? 'Связь с сервером: OK.' : 'Ответ сервера: не OK.';
      statusMsg.className = 'msg ' + (data.ok ? 'ok' : 'err');
      rawExtra.textContent = JSON.stringify(data, null, 2);
      rawExtra.style.display = 'block';
    } catch (e) {
      statusMsg.textContent = String(e.message || e);
      statusMsg.className = 'msg err';
    }
    setBusy(btn, false);
  };

  document.getElementById('btnGc').onclick = async function () {
    const btn = this;
    if (!confirm('Запустить очистку каталога STORAGE по лимиту STORAGE_MAX_GB?')) return;
    setBusy(btn, true);
    statusMsg.textContent = '';
    rawExtra.style.display = 'none';
    try {
      const data = await fetchJson('/api/queue/run_gc', { method: 'POST' });
      rawExtra.textContent = JSON.stringify(data, null, 2);
      rawExtra.style.display = 'block';
      statusMsg.textContent = 'Очистка выполнена (см. блок ниже).';
      statusMsg.className = 'msg ok';
    } catch (e) {
      statusMsg.textContent = String(e.message || e);
      statusMsg.className = 'msg err';
    }
    setBusy(btn, false);
  };

  async function serviceAction(action){
    const fd = new FormData();
    fd.append('action', action);
    return fetchJson('/api/service/action', { method: 'POST', body: fd });
  }

  async function loadStorageConfig(){
    try{
      const data = await fetchJson('/api/storage/config');
      if (storageRootInput) storageRootInput.value = data.storage_root || '';
    }catch(_e){}
  }

  document.getElementById('btnServiceStatus').onclick = async function () {
    const btn = this;
    setBusy(btn, true);
    try {
      const data = await fetchJson('/api/service/status');
      const suffix = data.mode === 'manual' ? ' (запущен вручную, не systemd)' : '';
      statusMsg.textContent = 'Сервис: ' + data.service + ' / ' + data.state + suffix;
      statusMsg.className = 'msg ' + (data.active ? 'ok' : 'err');
    } catch (e) {
      statusMsg.textContent = String(e.message || e);
      statusMsg.className = 'msg err';
    }
    setBusy(btn, false);
  };

  document.getElementById('btnServiceStart').onclick = async function () {
    const btn = this; setBusy(btn, true);
    try {
      const data = await serviceAction('start');
      statusMsg.textContent = data.ok ? 'Сервис запущен.' : ('Ошибка: ' + (data.message || ''));
      statusMsg.className = 'msg ' + (data.ok ? 'ok' : 'err');
    } catch (e) {
      statusMsg.textContent = String(e.message || e);
      statusMsg.className = 'msg err';
    }
    setBusy(btn, false);
  };

  document.getElementById('btnServiceStop').onclick = async function () {
    const btn = this; setBusy(btn, true);
    try {
      const data = await serviceAction('stop');
      statusMsg.textContent = data.ok ? 'Сервис остановлен.' : ('Ошибка: ' + (data.message || ''));
      statusMsg.className = 'msg ' + (data.ok ? 'ok' : 'err');
    } catch (e) {
      statusMsg.textContent = String(e.message || e);
      statusMsg.className = 'msg err';
    }
    setBusy(btn, false);
  };

  document.getElementById('btnServiceRestart').onclick = async function () {
    const btn = this; setBusy(btn, true);
    try {
      const data = await serviceAction('restart');
      statusMsg.textContent = data.ok ? 'Сервис перезапущен.' : ('Ошибка: ' + (data.message || ''));
      statusMsg.className = 'msg ' + (data.ok ? 'ok' : 'err');
    } catch (e) {
      statusMsg.textContent = String(e.message || e);
      statusMsg.className = 'msg err';
    }
    setBusy(btn, false);
  };

  document.getElementById('btnOpenFolder').onclick = async function () {
    const btn = this; setBusy(btn, true);
    try {
      const data = await fetchJson('/api/storage/open', { method: 'POST' });
      statusMsg.textContent = data.ok ? ('Открыта папка: ' + data.message) : ('Не удалось открыть: ' + data.message);
      statusMsg.className = 'msg ' + (data.ok ? 'ok' : 'err');
    } catch (e) {
      statusMsg.textContent = String(e.message || e);
      statusMsg.className = 'msg err';
    }
    setBusy(btn, false);
  };

  document.getElementById('btnSaveStorageRoot').onclick = async function () {
    const btn = this; setBusy(btn, true);
    try {
      const fd = new FormData();
      fd.append('storage_root', (storageRootInput && storageRootInput.value) ? storageRootInput.value : '');
      const data = await fetchJson('/api/storage/config', { method: 'POST', body: fd });
      statusMsg.textContent = 'Папка сохранена: ' + (data.storage_root || '');
      statusMsg.className = 'msg ok';
    } catch (e) {
      statusMsg.textContent = String(e.message || e);
      statusMsg.className = 'msg err';
    }
    setBusy(btn, false);
  };

  document.getElementById('f').onsubmit = async function (e) {
    e.preventDefault();
    const fd = new FormData(e.target);
    const file = fd.get('image');
    const submit = document.getElementById('btnSubmit');
    formMsg.textContent = '';
    formMsg.className = 'msg';
    if (!file || !file.size) {
      formMsg.textContent = 'Выберите файл изображения.';
      formMsg.className = 'msg err';
      return;
    }
    setBusy(submit, true);
    try {
      const r = await fetch('/api/local/enqueue', { method: 'POST', body: fd });
      const t = await r.text();
      let data;
      try { data = JSON.parse(t); } catch (x) { data = { raw: t }; }
      if (!r.ok) throw new Error((data && data.detail) || t);
      formMsg.textContent = data.enqueued ? 'Добавлено в очередь.' : 'Дубликат (уже в очереди по файлу).';
      formMsg.className = 'msg ok';
    } catch (err) {
      formMsg.textContent = String(err.message || err);
      formMsg.className = 'msg err';
    }
    setBusy(submit, false);
  };
  loadStorageConfig();
  </script>
</body>
</html>"""


@app.get("/cameras", response_class=HTMLResponse)
def ui_cameras():
    return """<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>QRPass Edge / Камеры</title>
  <style>
    body { font-family: "Segoe UI", Inter, system-ui, sans-serif; max-width: 1080px; margin: 1rem auto; padding: 0 1rem; background: #eef1f4; color:#1f2732; }
    .card { background: #fff; border: 1px solid #d7dee6; border-radius: 12px; padding: 1rem 1.1rem; margin-bottom: 1rem; box-shadow: 0 1px 3px rgba(0,0,0,.04); }
    h1 { margin: 0 0 .4rem; font-size: 1.3rem; }
    .muted { color: #5c6570; font-size: .9rem; margin: 0 0 1rem; }
    table { width: 100%; border-collapse: collapse; font-size: .9rem; }
    th, td { border-bottom: 1px solid #eceff3; padding: .45rem; text-align: left; vertical-align: top; }
    th { color: #5c6570; font-size: .78rem; text-transform: uppercase; }
    input[type=text], input[type=password] { width: 100%; max-width: 22rem; padding: .45rem; border: 1px solid #d9dde3; border-radius: 8px; }
    button { border: 1px solid #d7dee6; border-radius: 8px; padding: .45rem .8rem; cursor: pointer; background:#f7f9fc; }
    .primary { background: #1565c0; color: #fff; border-color:#1565c0; }
    .danger { background: #fff; color: #b71c1c; border: 1px solid #ffcdd2; }
    .ok { color: #2e7d32; font-weight: 600; }
    .bad { color: #c62828; font-weight: 600; }
    .row { margin-bottom: .55rem; }
    .grid { display: grid; gap: .6rem; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); }
    .checks { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: .4rem; margin: .5rem 0; }
    .checks label { display: block; padding: .35rem .45rem; border: 1px solid #e4e8ed; border-radius: 8px; background: #fafbfd; }
    .preview { width: 220px; height: 124px; object-fit: cover; border: 1px solid #d9dde3; border-radius: 8px; background: #f1f3f6; }
    .actions button { margin-right: .35rem; margin-bottom:.25rem; }
    .toolbar { display:flex; flex-wrap: wrap; gap:.5rem; align-items:center; margin-bottom:.5rem; }
  </style>
</head>
<body>
  <div class="card">
    <h1>Камеры (локально)</h1>
    <p class="muted">Добавление/редактирование камер и выбор проверок на мини‑ПК. Статус online/offline считается по heartbeat.</p>
    <p><a href="/">← Назад в панель</a> • <a href="/events">Журнал сработок</a></p>
  </div>
  <div class="card">
    <h2>Новая / редактирование</h2>
    <form id="camForm">
      <input type="hidden" name="camera_id" id="camera_id" value="">
      <div class="grid">
        <div class="row"><label>Имя камеры</label><br/><input type="text" id="name" name="name" required></div>
        <div class="row"><label>RTSP/URL</label><br/><input type="text" id="address" name="address"></div>
        <div class="row"><label>Логин</label><br/><input type="text" id="username" name="username"></div>
        <div class="row"><label>Пароль</label><br/><input type="password" id="password" name="password"></div>
      </div>
      <div class="checks">
        <label><input type="checkbox" id="chk_color" value="color"> Контроль цвета одежды</label>
        <label><input type="checkbox" id="chk_perimeter" value="perimeter"> Контроль периметра</label>
        <label><input type="checkbox" id="chk_count_live" value="count_live"> Подсчёт живых</label>
        <label><input type="checkbox" id="chk_count_dead" value="count_dead"> Подсчёт трупов</label>
      </div>
      <div class="row"><label><input type="checkbox" id="enabled" checked> Включена</label></div>
      <button class="primary" type="submit">Сохранить</button>
      <button type="button" id="resetBtn">Сбросить</button>
    </form>
    <p id="msg"></p>
  </div>
  <div class="card">
    <h2>Список камер + Preview</h2>
    <div class="toolbar">
      <button type="button" id="refreshBtn">Обновить</button>
    </div>
    <table>
      <thead><tr><th>ID</th><th>Камера</th><th>Статус</th><th>Проверки</th><th>Preview</th><th>Действия</th></tr></thead>
      <tbody id="tb"></tbody>
    </table>
  </div>
  <script>
  const tb = document.getElementById('tb');
  const msg = document.getElementById('msg');
  const f = document.getElementById('camForm');
  let rows = [];
  const CHECK_IDS = ['color','perimeter','count_live','count_dead'];
  function esc(s){ return (s||'').replace(/</g,'&lt;'); }
  function setMsg(t, ok){ msg.textContent=t||''; msg.className=ok?'ok':'bad'; }
  function normalizeChecks(arr){
    const out = [];
    (arr || []).forEach(v => {
      const s = String(v || '').trim().toLowerCase();
      if(!s) return;
      if (['color','colors','контроль цвета одежды','одежда','uniform'].includes(s)) { if(!out.includes('color')) out.push('color'); return; }
      if (['perimeter','контроль периметра','периметр','zone'].includes(s)) { if(!out.includes('perimeter')) out.push('perimeter'); return; }
      if (['count_live','подсчёт живых','подсчет живых','live','живые'].includes(s)) { if(!out.includes('count_live')) out.push('count_live'); return; }
      if (['count_dead','подсчёт трупов','подсчет трупов','dead','трупы'].includes(s)) { if(!out.includes('count_dead')) out.push('count_dead'); return; }
    });
    return out;
  }
  function setChecks(v){
    const norm = normalizeChecks(v || []);
    CHECK_IDS.forEach(id => { const el = document.getElementById('chk_' + id); if(el) el.checked = !!norm.includes(id); });
  }
  function getChecks(){
    return CHECK_IDS.filter(id => { const el = document.getElementById('chk_' + id); return !!(el && el.checked); });
  }
  function resetForm(){
    f.camera_id.value=''; f.name.value=''; f.address.value=''; f.username.value=''; f.password.value='';
    setChecks([]); f.enabled.checked=true; setMsg('', true);
  }
  async function j(url, opt){
    const r = await fetch(url, opt||{});
    const t = await r.text(); let d;
    try { d = JSON.parse(t); } catch(e){ d = {raw:t}; }
    if(!r.ok) throw new Error((d && d.detail) || t || r.statusText);
    return d;
  }
  function render(){
    tb.innerHTML='';
    rows.forEach(r=>{
      const imgUrl = '/api/cameras/' + r.id + '/preview?t=' + Date.now();
      const tr=document.createElement('tr');
      tr.innerHTML =
        '<td>'+r.id+'</td>'+
        '<td><b>'+esc(r.name)+'</b><br><small>'+esc(r.address||'')+'</small></td>'+
        '<td>'+(r.status==='online' ? '<span class="ok">online</span>' : '<span class="bad">offline</span>')+'</td>'+
        '<td>'+esc((r.checks||[]).join(', '))+'</td>'+
        '<td><img class="preview" src="'+imgUrl+'" onerror="this.style.opacity=0.25" alt="preview"></td>'+
        '<td class="actions"><button data-e="'+r.id+'">Ред.</button> <button data-c="'+r.id+'">Сбросить правила</button> <button class="danger" data-d="'+r.id+'">Удалить</button></td>';
      tb.appendChild(tr);
    });
  }
  async function load(){ rows = await j('/api/cameras'); render(); }
  document.getElementById('refreshBtn').onclick = ()=>load().catch(e=>setMsg(String(e), false));
  document.getElementById('resetBtn').onclick = resetForm;
  tb.onclick = async (e)=>{
    const eid = e.target.getAttribute('data-e');
    const did = e.target.getAttribute('data-d');
    const cid = e.target.getAttribute('data-c');
    if(eid){
      const x = rows.find(v => String(v.id)===String(eid)); if(!x) return;
      f.camera_id.value=x.id; f.name.value=x.name||''; f.address.value=x.address||'';
      f.username.value=x.username||''; f.password.value=x.password||'';
      setChecks(x.checks || []); f.enabled.checked=!!x.enabled;
      setMsg('Режим редактирования: камера #' + x.id + ' (' + (x.name||'') + ')', true);
      f.scrollIntoView({behavior:'smooth', block:'start'});
      return;
    }
    if(did){
      if(!confirm('Удалить камеру?')) return;
      await j('/api/cameras/'+did, {method:'DELETE'});
      await load(); setMsg('Камера удалена', true);
    }
    if(cid){
      if(!confirm('Сбросить правила только у этой камеры?')) return;
      await j('/api/cameras/'+cid+'/clear_checks', {method:'POST'});
      await load(); setMsg('Правила камеры сброшены', true);
    }
  };
  f.onsubmit = async (e)=>{
    e.preventDefault();
    const fd = new FormData();
    fd.append('name', f.name.value || '');
    fd.append('address', f.address.value || '');
    fd.append('username', f.username.value || '');
    fd.append('password', f.password.value || '');
    fd.append('checks_csv', getChecks().join(','));
    fd.append('enabled', f.enabled.checked ? '1' : '0');
    const id = f.camera_id.value;
    const url = id ? ('/api/cameras/' + id) : '/api/cameras';
    await j(url, { method:'POST', body: fd });
    await load(); setMsg('Сохранено', true);
    if(!id) resetForm();
  };
  load().catch(e=>setMsg(String(e), false));
  setInterval(()=>{ document.querySelectorAll('img.preview').forEach(img=>{ img.src = img.src.split('?')[0] + '?t=' + Date.now(); }); }, 3000);
  </script>
</body>
</html>"""


@app.get("/events", response_class=HTMLResponse)
def ui_events():
    return """<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>QRPass Edge / Журнал сработок</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 1080px; margin: 1rem auto; padding: 0 1rem; background: #f5f6f8; }
    .card { background: #fff; border: 1px solid #e2e5e9; border-radius: 10px; padding: 1rem; margin-bottom: 1rem; }
    .grid { display: grid; gap: .6rem; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); align-items: end; }
    label { display:block; font-size:.82rem; color:#5c6570; margin-bottom:.2rem; }
    input { width:100%; padding:.45rem; border:1px solid #d9dde3; border-radius:8px; }
    button { border:0; border-radius:8px; padding:.45rem .8rem; cursor:pointer; background:#1565c0; color:#fff; }
    table { width: 100%; border-collapse: collapse; font-size: .88rem; }
    th, td { border-bottom: 1px solid #eceff3; padding: .45rem; text-align: left; vertical-align: top; }
    th { color: #5c6570; font-size: .78rem; text-transform: uppercase; }
    .muted { color:#5c6570; font-size:.9rem; }
    .mono { font-family: ui-monospace, monospace; font-size:.78rem; word-break: break-all; }
  </style>
</head>
<body>
  <div class="card">
    <h1>Журнал сработок</h1>
    <p class="muted">Фильтры по дате, камере и типу нарушения. Источник: локальная очередь edge.</p>
    <p><a href="/">← Назад в панель</a> • <a href="/cameras">Камеры</a></p>
  </div>
  <div class="card">
    <div class="grid">
      <div><label>Дата от</label><input id="date_from" type="date"/></div>
      <div><label>Дата до</label><input id="date_to" type="date"/></div>
      <div><label>Камера</label><input id="camera_name" type="text" placeholder="Б2.Вход1"/></div>
      <div><label>Тип нарушения</label><input id="violation_type" type="text" placeholder="Нет униформы"/></div>
      <div><label>Лимит</label><input id="limit" type="number" value="100" min="10" max="500"/></div>
      <div><button id="applyBtn" type="button">Применить фильтры</button></div>
    </div>
  </div>
  <div class="card">
    <table>
      <thead><tr><th>ID</th><th>Время</th><th>Камера</th><th>Тип</th><th>Статус</th><th>Файл</th></tr></thead>
      <tbody id="tb"></tbody>
    </table>
    <p id="msg" class="muted"></p>
  </div>
  <script>
  const tb = document.getElementById('tb');
  const msg = document.getElementById('msg');
  function esc(s){ return (s||'').replace(/</g,'&lt;'); }
  function fmt(ts){ const d = new Date((Number(ts)||0)*1000); return isNaN(d)?String(ts):d.toLocaleString('ru-RU'); }
  async function load(){
    msg.textContent = 'Загрузка...';
    const q = new URLSearchParams({
      date_from: document.getElementById('date_from').value || '',
      date_to: document.getElementById('date_to').value || '',
      camera_name: document.getElementById('camera_name').value || '',
      violation_type: document.getElementById('violation_type').value || '',
      limit: document.getElementById('limit').value || '100',
    });
    const r = await fetch('/api/events?' + q.toString(), { headers: { 'Accept': 'application/json' } });
    const t = await r.text(); let data;
    try { data = JSON.parse(t); } catch(e){ throw new Error(t); }
    if(!r.ok){ throw new Error((data && data.detail) || t || r.statusText); }
    tb.innerHTML = '';
    (data || []).forEach(x => {
      const tr = document.createElement('tr');
      tr.innerHTML =
        '<td>'+x.id+'</td>'+
        '<td>'+fmt(x.created_at)+'</td>'+
        '<td>'+esc(x.camera_name||'')+'</td>'+
        '<td>'+esc(x.violation_type||'')+'</td>'+
        '<td>'+esc(x.status||'')+'</td>'+
        '<td class="mono">'+esc(x.file_path||'')+'</td>';
      tb.appendChild(tr);
    });
    msg.textContent = 'Найдено: ' + (data || []).length;
  }
  document.getElementById('applyBtn').onclick = () => load().catch(e => { msg.textContent = String(e); });
  load().catch(e => { msg.textContent = String(e); });
  </script>
</body>
</html>"""


@app.get("/logs", response_class=HTMLResponse)
def ui_logs():
    return """<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>QRPass Edge / Логи</title>
  <style>
    body { font-family: "Segoe UI", Inter, system-ui, sans-serif; max-width: 1100px; margin: 1rem auto; padding: 0 1rem; background:#eef1f4; }
    .card { background:#fff; border:1px solid #d7dee6; border-radius:12px; padding:1rem 1.1rem; margin-bottom:1rem; }
    .muted { color:#5f6b7a; font-size:.9rem; }
    button { border:1px solid #d7dee6; border-radius:8px; padding:.45rem .8rem; background:#f7f9fc; cursor:pointer; }
    pre { background:#192231; color:#e2e8f0; border-radius:10px; padding:.75rem; max-height:65vh; overflow:auto; font-size:.8rem; }
  </style>
</head>
<body>
  <div class="card">
    <h1>Логи edge</h1>
    <p class="muted"><a href="/">← Назад</a> • Файловый лог сервиса с ротацией.</p>
    <button id="btnLoad">Обновить</button>
    <p id="meta" class="muted"></p>
  </div>
  <div class="card"><pre id="out">Загрузка...</pre></div>
  <script>
  async function load(){
    const r = await fetch('/api/logs/recent?lines=350', {headers:{'Accept':'application/json'}});
    const t = await r.text(); let d;
    try { d = JSON.parse(t); } catch(e){ d = {text:t}; }
    if(!r.ok){ throw new Error((d && d.detail) || t || r.statusText); }
    document.getElementById('meta').textContent = 'Файл: ' + (d.path || '');
    document.getElementById('out').textContent = d.text || '(пусто)';
  }
  document.getElementById('btnLoad').onclick = () => load().catch(e => { document.getElementById('out').textContent = String(e); });
  load().catch(e => { document.getElementById('out').textContent = String(e); });
  </script>
</body>
</html>"""


@app.get("/files", response_class=HTMLResponse)
def ui_files():
    return """<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>QRPass Edge / Файлы</title>
  <style>
    body { font-family: "Segoe UI", Inter, system-ui, sans-serif; max-width: 1100px; margin: 1rem auto; padding: 0 1rem; background:#eef1f4; }
    .card { background:#fff; border:1px solid #d7dee6; border-radius:12px; padding:1rem 1.1rem; margin-bottom:1rem; }
    .muted { color:#5f6b7a; font-size:.9rem; }
    button { border:1px solid #d7dee6; border-radius:8px; padding:.45rem .8rem; background:#f7f9fc; cursor:pointer; }
    table { width:100%; border-collapse:collapse; font-size:.88rem; }
    th, td { border-bottom:1px solid #e7edf3; padding:.45rem; text-align:left; vertical-align:top; }
    th { color:#5f6b7a; font-size:.78rem; text-transform:uppercase; }
    .mono { font-family: ui-monospace, monospace; font-size:.78rem; word-break:break-all; }
  </style>
</head>
<body>
  <div class="card">
    <h1>Файлы нарушений</h1>
    <p class="muted"><a href="/">← Назад</a> • Просмотр содержимого папки хранения прямо из программы.</p>
    <button id="btnLoad">Обновить список</button>
    <p id="meta" class="muted"></p>
  </div>
  <div class="card">
    <table>
      <thead><tr><th>Имя</th><th>Размер</th><th>Изменён</th><th>Путь</th><th>Действие</th></tr></thead>
      <tbody id="tb"></tbody>
    </table>
    <p id="msg" class="muted"></p>
  </div>
  <script>
  const tb = document.getElementById('tb');
  const msg = document.getElementById('msg');
  const meta = document.getElementById('meta');
  function esc(s){ return (s||'').replace(/</g,'&lt;'); }
  function fmtSize(n){
    const x = Number(n||0);
    if (x < 1024) return x + ' B';
    if (x < 1024*1024) return (x/1024).toFixed(1) + ' KB';
    return (x/1024/1024).toFixed(2) + ' MB';
  }
  function fmtTime(ts){ const d = new Date((Number(ts)||0)*1000); return isNaN(d)?String(ts):d.toLocaleString('ru-RU'); }
  async function load(){
    msg.textContent = 'Загрузка...';
    const r = await fetch('/api/storage/files?limit=500', {headers:{'Accept':'application/json'}});
    const t = await r.text(); let d;
    try { d = JSON.parse(t); } catch(e){ throw new Error(t); }
    if(!r.ok){ throw new Error((d && d.detail) || t || r.statusText); }
    meta.textContent = 'Папка: ' + (d.root || '');
    tb.innerHTML = '';
    (d.files || []).forEach(f => {
      const href = '/api/storage/file?rel_path=' + encodeURIComponent(f.rel_path || '');
      const tr = document.createElement('tr');
      tr.innerHTML =
        '<td>'+esc(f.name||'')+'</td>'+
        '<td>'+fmtSize(f.size)+'</td>'+
        '<td>'+fmtTime(f.mtime)+'</td>'+
        '<td class="mono">'+esc(f.rel_path||'')+'</td>'+
        '<td><a href="'+href+'" target="_blank" style="display:inline-block; padding:.3rem .6rem; background:#1565c0; color:#fff; text-decoration:none; border-radius:6px; font-size:.8rem;">Смотреть фото</a></td>';
      tb.appendChild(tr);
    });
    msg.textContent = 'Файлов: ' + (d.files || []).length;
  }
  document.getElementById('btnLoad').onclick = () => load().catch(e => { msg.textContent = String(e); });
  load().catch(e => { msg.textContent = String(e); });
  </script>
</body>
</html>"""


def run():
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.edge_ui_host,
        port=settings.edge_ui_port,
        log_level="info",
    )


if __name__ == "__main__":
    run()
