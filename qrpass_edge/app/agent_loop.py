from __future__ import annotations

import logging
import sqlite3
import threading
import time
import json
from pathlib import Path

from app import queue_db
from app.config import settings
from app.storage_gc import run_storage_gc
from app.uploader import post_heartbeat, post_violation, post_pig_count_event

_log = logging.getLogger(__name__)


def agent_thread_body(stop: threading.Event, conn: sqlite3.Connection) -> None:
    gc_every = 0
    last_hb = 0.0
    last_hb_error_log = 0.0
    last_hb_error_text = ""
    while not stop.wait(settings.agent_poll_seconds):
        try:
            now = time.time()
            if (
                settings.upstream_enabled
                and settings.heartbeat_interval_seconds > 0
                and (now - last_hb) >= settings.heartbeat_interval_seconds
            ):
                hb = post_heartbeat(
                    camera_name=settings.default_camera_name,
                    site_name=settings.site_name,
                    rule_summary="edge-online",
                )
                if not hb.ok:
                    err_text = (hb.message or "")[:220]
                    cooldown = max(1.0, float(settings.heartbeat_error_log_cooldown_seconds or 60.0))
                    should_log = (
                        err_text != last_hb_error_text
                        or (now - last_hb_error_log) >= cooldown
                    )
                    if should_log:
                        _log.warning(
                            "heartbeat error: http=%s %s | SERVER_URL=%s",
                            hb.http_code,
                            err_text,
                            settings.server_url,
                        )
                        last_hb_error_log = now
                        last_hb_error_text = err_text
                last_hb = now

            ev = queue_db.fetch_next_pending(conn)
            if ev:
                if settings.upstream_enabled:
                    p = Path(ev.file_path)
                    if ev.event_type == "pig_count":
                        n = queue_db.mark_sending(conn, ev.id)
                        if n:
                            try:
                                payload = json.loads(ev.payload_json or "{}")
                            except Exception:
                                payload = {}
                            res = post_pig_count_event(
                                camera_name=ev.camera_name,
                                site_name=settings.site_name,
                                count=int(payload.get("count") or 0),
                                ts_from=float(payload.get("ts_from") or time.time()),
                                ts_to=float(payload.get("ts_to") or time.time()),
                                direction=str(payload.get("direction") or "up"),
                                line_y_ratio=float(payload.get("line_y_ratio") or 0.58),
                                preview_path=p if p.is_file() else None,
                            )
                            if res.ok:
                                queue_db.mark_sent(conn, ev.id)
                                _log.info("Отправлено pig_count событие %s", ev.id)
                            else:
                                queue_db.mark_failed(conn, ev.id, res.http_code, res.message)
                                _log.warning(
                                    "Ошибка отправки pig_count %s: http=%s %s",
                                    ev.id,
                                    res.http_code,
                                    res.message[:200],
                                )
                    elif not p.is_file():
                        queue_db.mark_skipped_no_file(conn, ev.id, "local file missing")
                        _log.warning("Событие %s: файл отсутствует %s", ev.id, ev.file_path)
                    else:
                        n = queue_db.mark_sending(conn, ev.id)
                        if n:
                            res = post_violation(
                                file_path=p,
                                camera_name=ev.camera_name,
                                violation_type=ev.violation_type,
                                site_name=settings.site_name,
                            )
                            if res.ok:
                                queue_db.mark_sent(conn, ev.id)
                                _log.info("Отправлено событие %s", ev.id)
                            else:
                                queue_db.mark_failed(conn, ev.id, res.http_code, res.message)
                                _log.warning(
                                    "Ошибка отправки %s: http=%s %s",
                                    ev.id,
                                    res.http_code,
                                    res.message[:200],
                                )
            gc_every += 1
            if gc_every >= 60:
                gc_every = 0
                summary = run_storage_gc(conn)
                if summary.get("deleted_files"):
                    _log.info("storage_gc: %s", summary)
        except Exception:
            _log.exception("agent_loop")
