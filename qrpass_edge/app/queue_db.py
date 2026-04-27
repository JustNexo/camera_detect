from __future__ import annotations

import sqlite3
import threading
import time
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


_lock = threading.Lock()


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        PRAGMA journal_mode=WAL;

        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at REAL NOT NULL,
            event_type TEXT NOT NULL,
            camera_name TEXT NOT NULL,
            violation_type TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_sha256 TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            retry_count INTEGER NOT NULL DEFAULT 0,
            next_retry_at REAL NOT NULL,
            last_error TEXT,
            last_http_code INTEGER,
            updated_at REAL NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_events_status_next ON events(status, next_retry_at);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_events_dedup ON events(file_sha256, event_type, camera_name);

        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """
    )
    conn.commit()
    cols = conn.execute("PRAGMA table_info(events)").fetchall()
    col_names = {str(r["name"]) for r in cols}
    if "payload_json" not in col_names:
        conn.execute("ALTER TABLE events ADD COLUMN payload_json TEXT NOT NULL DEFAULT ''")
        conn.commit()


@dataclass
class QueuedEvent:
    id: int
    event_type: str
    camera_name: str
    violation_type: str
    file_path: str
    payload_json: str


def enqueue_violation(
    conn: sqlite3.Connection,
    *,
    camera_name: str,
    violation_type: str,
    file_path: Path,
    file_sha256: str,
) -> bool:
    """True если вставили новую строку, False если дубликат."""
    now = time.time()
    fp = str(file_path.resolve())
    with _lock:
        try:
            conn.execute(
                """
                INSERT INTO events (
                    created_at, event_type, camera_name, violation_type,
                    file_path, file_sha256, status, retry_count, next_retry_at, updated_at
                ) VALUES (?, 'violation', ?, ?, ?, ?, 'pending', 0, ?, ?)
                """,
                (now, camera_name, violation_type, fp, file_sha256, now, now),
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            conn.rollback()
            return False


def enqueue_pig_count(
    conn: sqlite3.Connection,
    *,
    camera_name: str,
    count: int,
    ts_from: float,
    ts_to: float,
    direction: str,
    line_y_ratio: float,
    file_path: Path | None,
    event_sha256: str,
) -> bool:
    """True если вставили новую строку, False если дубликат."""
    now = time.time()
    fp = str(file_path.resolve()) if file_path else ""
    payload = {
        "count": int(count),
        "ts_from": float(ts_from),
        "ts_to": float(ts_to),
        "direction": str(direction or "up"),
        "line_y_ratio": float(line_y_ratio),
    }
    with _lock:
        try:
            conn.execute(
                """
                INSERT INTO events (
                    created_at, event_type, camera_name, violation_type,
                    file_path, file_sha256, payload_json, status, retry_count, next_retry_at, updated_at
                ) VALUES (?, 'pig_count', ?, 'pig_count', ?, ?, ?, 'pending', 0, ?, ?)
                """,
                (now, camera_name, fp, event_sha256, json.dumps(payload, ensure_ascii=False), now, now),
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            conn.rollback()
            return False


def fetch_next_pending(conn: sqlite3.Connection, now: float | None = None) -> QueuedEvent | None:
    now = now or time.time()
    with _lock:
        row = conn.execute(
            """
            SELECT id, event_type, camera_name, violation_type, file_path, payload_json
            FROM events
            WHERE status = 'pending' AND next_retry_at <= ?
            ORDER BY id ASC
            LIMIT 1
            """,
            (now,),
        ).fetchone()
        if not row:
            return None
        return QueuedEvent(
            id=int(row["id"]),
            event_type=str(row["event_type"] or "violation"),
            camera_name=str(row["camera_name"]),
            violation_type=str(row["violation_type"]),
            file_path=str(row["file_path"]),
            payload_json=str(row["payload_json"] or ""),
        )


def mark_sending(conn: sqlite3.Connection, event_id: int) -> int:
    now = time.time()
    with _lock:
        cur = conn.execute(
            "UPDATE events SET status='sending', updated_at=? WHERE id=? AND status='pending'",
            (now, event_id),
        )
        conn.commit()
        return cur.rowcount or 0


def mark_sent(conn: sqlite3.Connection, event_id: int) -> None:
    now = time.time()
    with _lock:
        conn.execute(
            "UPDATE events SET status='sent', last_error=NULL, last_http_code=200, updated_at=? WHERE id=?",
            (now, event_id),
        )
        conn.commit()


def mark_failed(conn: sqlite3.Connection, event_id: int, http_code: int | None, err: str) -> None:
    now = time.time()
    delays = (10.0, 30.0, 120.0, 300.0, 900.0)
    with _lock:
        row = conn.execute("SELECT retry_count FROM events WHERE id=?", (event_id,)).fetchone()
        rc = int(row["retry_count"]) if row else 0
        delay = delays[min(rc, len(delays) - 1)]
        conn.execute(
            """
            UPDATE events SET
                status='pending',
                retry_count=retry_count+1,
                next_retry_at=?,
                last_error=?,
                last_http_code=?,
                updated_at=?
            WHERE id=?
            """,
            (now + delay, (err or "")[:2000], http_code, now, event_id),
        )
        conn.commit()


def mark_skipped_no_file(conn: sqlite3.Connection, event_id: int, err: str) -> None:
    now = time.time()
    with _lock:
        conn.execute(
            """
            UPDATE events SET
                status='skipped_no_file',
                last_error=?,
                updated_at=?
            WHERE id=?
            """,
            ((err or "")[:2000], now, event_id),
        )
        conn.commit()


def stats(conn: sqlite3.Connection) -> dict[str, Any]:
    with _lock:
        rows = conn.execute(
            "SELECT status, COUNT(*) AS c FROM events GROUP BY status"
        ).fetchall()
        total = conn.execute("SELECT COUNT(*) AS c FROM events").fetchone()
    out: dict[str, int] = {}
    for r in rows:
        out[str(r["status"])] = int(r["c"])
    out["total"] = int(total["c"]) if total else 0
    return out


def recent_events(conn: sqlite3.Connection, limit: int = 30) -> list[dict[str, Any]]:
    with _lock:
        rows = conn.execute(
            """
            SELECT id, created_at, event_type, camera_name, violation_type, status, retry_count,
                   last_error, last_http_code, file_path
            FROM events
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def filtered_events(
    conn: sqlite3.Connection,
    *,
    limit: int = 100,
    camera_name: str = "",
    violation_type: str = "",
    created_from_ts: float | None = None,
    created_to_ts: float | None = None,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if camera_name.strip():
        clauses.append("camera_name = ?")
        params.append(camera_name.strip())
    if violation_type.strip():
        clauses.append("violation_type = ?")
        params.append(violation_type.strip())
    if created_from_ts is not None:
        clauses.append("created_at >= ?")
        params.append(float(created_from_ts))
    if created_to_ts is not None:
        clauses.append("created_at <= ?")
        params.append(float(created_to_ts))

    where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"""
        SELECT id, created_at, event_type, camera_name, violation_type, status, retry_count,
               last_error, last_http_code, file_path
        FROM events
        {where_sql}
        ORDER BY id DESC
        LIMIT ?
    """
    with _lock:
        rows = conn.execute(sql, (*params, int(limit))).fetchall()
    return [dict(r) for r in rows]


def get_setting(conn: sqlite3.Connection, key: str, default: str = "") -> str:
    with _lock:
        row = conn.execute("SELECT value FROM app_settings WHERE key=?", (key,)).fetchone()
    if not row:
        return default
    return str(row["value"] or default)


def set_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    with _lock:
        conn.execute(
            """
            INSERT INTO app_settings(key, value) VALUES(?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
            """,
            (key, value),
        )
        conn.commit()
