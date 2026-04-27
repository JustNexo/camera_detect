from __future__ import annotations

import logging
import os
import sqlite3
from pathlib import Path

from app.config import settings

_log = logging.getLogger(__name__)


def _dir_size_bytes(root: Path) -> int:
    total = 0
    for dirpath, _dirnames, filenames in os.walk(root):
        for fn in filenames:
            fp = Path(dirpath) / fn
            try:
                total += fp.stat().st_size
            except OSError:
                pass
    return total


def _list_files_by_mtime(root: Path) -> list[Path]:
    out: list[tuple[float, Path]] = []
    if not root.is_dir():
        return []
    for dirpath, _dirnames, filenames in os.walk(root):
        for fn in filenames:
            fp = Path(dirpath) / fn
            try:
                out.append((fp.stat().st_mtime, fp))
            except OSError:
                pass
    out.sort(key=lambda x: x[0])
    return [p for _mt, p in out]


def protected_paths(conn: sqlite3.Connection, storage_root: Path) -> set[str]:
    """Пути файлов, которые нельзя удалять (ещё в очереди на отправку)."""
    root = storage_root.resolve()
    rows = conn.execute(
        """
        SELECT file_path FROM events
        WHERE status IN ('pending', 'sending')
        """
    ).fetchall()
    prot: set[str] = set()
    for r in rows:
        try:
            prot.add(str(Path(str(r["file_path"])).resolve()))
        except OSError:
            prot.add(str(r["file_path"]))
    # только внутри storage_root
    return {p for p in prot if p.startswith(str(root) + os.sep) or p == str(root)}


def run_storage_gc(conn: sqlite3.Connection | None) -> dict[str, int | str]:
    """
    Если суммарный размер STORAGE_ROOT превышает STORAGE_MAX_GБ,
    удаляет самые старые файлы, не затрагивая pending/sending из очереди.
    """
    max_gb = float(settings.storage_max_gb or 0.0)
    if max_gb <= 0:
        return {"skipped": 1, "reason": "STORAGE_MAX_GB=0"}

    root = settings.storage_root
    root.mkdir(parents=True, exist_ok=True)
    max_bytes = int(max_gb * (1024**3))
    bytes_before = _dir_size_bytes(root)
    current = bytes_before
    if current <= max_bytes:
        return {"bytes_before": current, "deleted_files": 0, "bytes_after": current}

    prot = protected_paths(conn, root) if conn else set()
    candidates = _list_files_by_mtime(root)
    deleted = 0
    for fp in candidates:
        if current <= max_bytes:
            break
        try:
            rp = str(fp.resolve())
        except OSError:
            continue
        if rp in prot:
            continue
        try:
            sz = fp.stat().st_size
        except OSError:
            continue
        try:
            fp.unlink()
            current -= sz
            deleted += 1
        except OSError as e:
            _log.warning("Не удалось удалить %s: %s", fp, e)

    return {
        "bytes_before": bytes_before,
        "deleted_files": deleted,
        "bytes_after": _dir_size_bytes(root),
    }
