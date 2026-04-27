from __future__ import annotations

import json
import sqlite3
import threading
import time
from typing import Any

from app.config import settings

_lock = threading.Lock()


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS cameras (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            address TEXT NOT NULL DEFAULT '',
            username TEXT NOT NULL DEFAULT '',
            password TEXT NOT NULL DEFAULT '',
            checks_json TEXT NOT NULL DEFAULT '[]',
            enabled INTEGER NOT NULL DEFAULT 1,
            last_seen REAL,
            last_error TEXT,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        );
        """
    )
    conn.commit()


def _parse_checks(raw: str) -> list[str]:
    try:
        data = json.loads(raw or "[]")
    except json.JSONDecodeError:
        data = []
    out: list[str] = []
    for x in data if isinstance(data, list) else []:
        s = str(x).strip()
        if s and s not in out:
            out.append(s)
    return out


def list_cameras(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    now = time.time()
    online_window = max(5, int(settings.camera_online_seconds))
    with _lock:
        rows = conn.execute(
            """
            SELECT id, name, address, username, password, checks_json, enabled,
                   last_seen, last_error, created_at, updated_at
            FROM cameras
            ORDER BY id ASC
            """
        ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        checks = _parse_checks(str(d.get("checks_json") or "[]"))
        last_seen = d.get("last_seen")
        is_online = bool(last_seen and (now - float(last_seen) <= online_window))
        out.append(
            {
                "id": int(d["id"]),
                "name": str(d["name"]),
                "address": str(d.get("address") or ""),
                "username": str(d.get("username") or ""),
                "password": str(d.get("password") or ""),
                "checks": checks,
                "enabled": bool(int(d.get("enabled") or 0)),
                "last_seen": last_seen,
                "last_error": str(d.get("last_error") or ""),
                "status": "online" if is_online else "offline",
            }
        )
    return out


def upsert_camera(
    conn: sqlite3.Connection,
    *,
    camera_id: int | None,
    name: str,
    address: str,
    username: str,
    password: str,
    checks: list[str],
    enabled: bool,
) -> dict[str, Any]:
    now = time.time()
    checks_json = json.dumps([x.strip() for x in checks if x.strip()], ensure_ascii=False)
    with _lock:
        if camera_id is None:
            cur = conn.execute(
                """
                INSERT INTO cameras(name, address, username, password, checks_json, enabled, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (name.strip(), address.strip(), username.strip(), password, checks_json, 1 if enabled else 0, now, now),
            )
            conn.commit()
            cid = int(cur.lastrowid)
        else:
            conn.execute(
                """
                UPDATE cameras
                SET name=?, address=?, username=?, password=?, checks_json=?, enabled=?, updated_at=?
                WHERE id=?
                """,
                (name.strip(), address.strip(), username.strip(), password, checks_json, 1 if enabled else 0, now, int(camera_id)),
            )
            conn.commit()
            cid = int(camera_id)
    row = get_camera(conn, cid)
    if not row:
        raise RuntimeError("camera_not_found_after_upsert")
    return row


def get_camera(conn: sqlite3.Connection, camera_id: int) -> dict[str, Any] | None:
    with _lock:
        row = conn.execute(
            """
            SELECT id, name, address, username, password, checks_json, enabled, last_seen, last_error
            FROM cameras WHERE id=?
            """,
            (int(camera_id),),
        ).fetchone()
    if not row:
        return None
    d = dict(row)
    return {
        "id": int(d["id"]),
        "name": str(d["name"]),
        "address": str(d.get("address") or ""),
        "username": str(d.get("username") or ""),
        "password": str(d.get("password") or ""),
        "checks": _parse_checks(str(d.get("checks_json") or "[]")),
        "enabled": bool(int(d.get("enabled") or 0)),
        "last_seen": d.get("last_seen"),
        "last_error": str(d.get("last_error") or ""),
    }


def delete_camera(conn: sqlite3.Connection, camera_id: int) -> bool:
    with _lock:
        cur = conn.execute("DELETE FROM cameras WHERE id=?", (int(camera_id),))
        conn.commit()
        return (cur.rowcount or 0) > 0


def reset_legacy_perimeter_checks(conn: sqlite3.Connection) -> int:
    with _lock:
        cur = conn.execute(
            """
            UPDATE cameras
            SET checks_json='[]', updated_at=?
            WHERE checks_json='["perimeter"]'
            """,
            (time.time(),),
        )
        conn.commit()
        return int(cur.rowcount or 0)


def clear_camera_checks(conn: sqlite3.Connection, camera_id: int) -> bool:
    with _lock:
        cur = conn.execute(
            "UPDATE cameras SET checks_json='[]', updated_at=? WHERE id=?",
            (time.time(), int(camera_id)),
        )
        conn.commit()
        return (cur.rowcount or 0) > 0


def touch_camera_seen(conn: sqlite3.Connection, camera_name: str, err: str = "") -> None:
    touch_camera_seen_with_meta(conn, camera_name=camera_name, err=err, address="", checks=[])


def touch_camera_seen_with_meta(
    conn: sqlite3.Connection,
    *,
    camera_name: str,
    err: str = "",
    address: str = "",
    checks: list[str] | None = None,
) -> None:
    now = time.time()
    name = camera_name.strip()
    if not name:
        return
    checks = checks or []
    checks_json = json.dumps([x.strip() for x in checks if x.strip()], ensure_ascii=False)
    addr = address.strip()
    with _lock:
        row = conn.execute(
            "SELECT id, address, checks_json FROM cameras WHERE name=?",
            (name,),
        ).fetchone()
        if row:
            current_addr = str(row["address"] or "")
            current_checks = str(row["checks_json"] or "[]")
            # Адрес обновляем только если в БД ещё пусто.
            new_addr = current_addr if current_addr.strip() else (addr or "")
            # Важно: не перетираем настройки проверок из UI heartbeat-данными.
            # Обновляем checks только если в БД пока пусто.
            has_current_checks = len(_parse_checks(current_checks)) > 0
            new_checks = current_checks if has_current_checks else (checks_json if checks else "[]")
            conn.execute(
                """
                UPDATE cameras
                SET last_seen=?, last_error=?, address=?, checks_json=?, updated_at=?
                WHERE name=?
                """,
                (now, (err or "")[:500], new_addr, new_checks, now, name),
            )
            conn.commit()
            return

        # Автообнаружение камеры: если пришёл heartbeat/stream от неизвестной камеры,
        # создаём запись, чтобы она появилась в локальном UI.
        conn.execute(
            """
            INSERT INTO cameras(name, address, username, password, checks_json, enabled, last_seen, last_error, created_at, updated_at)
            VALUES (?, ?, '', '', ?, 1, ?, ?, ?, ?)
            """,
            (name, addr, checks_json if checks else "[]", now, (err or "")[:500], now, now),
        )
        conn.commit()
