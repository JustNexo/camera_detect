"""
Постановка файла нарушения в локальную очередь (без запуска UI/агента).

Запуск из каталога qrpass_edge с активированным venv:

  python -m app.enqueue_violation --file ./shot.jpg --camera "ФФО-1" --type "Нет каски"

Опционально скопировать файл в STORAGE_ROOT (если детектор пишет во временный каталог):

  python -m app.enqueue_violation --file /tmp/x.jpg --camera "ФФО-1" --type "Тест" --copy-to-storage
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

from app.config import settings
from app.hashfile import sha256_file
from app import queue_db


def main() -> int:
    p = argparse.ArgumentParser(description="Добавить снимок в очередь QRPass Edge")
    p.add_argument("--file", required=True, type=Path, help="Путь к файлу изображения")
    p.add_argument("--camera", required=True, help="Имя камеры (как на сервере)")
    p.add_argument("--type", dest="violation_type", required=True, help="Тип нарушения")
    p.add_argument(
        "--copy-to-storage",
        action="store_true",
        help="Скопировать файл в STORAGE_ROOT перед постановкой в очередь",
    )
    args = p.parse_args()

    src = args.file.resolve()
    if not src.is_file():
        print(json.dumps({"ok": False, "error": "file_not_found", "path": str(src)}), file=sys.stderr)
        return 2

    target = src
    if args.copy_to_storage:
        settings.storage_root.mkdir(parents=True, exist_ok=True)
        suffix = src.suffix or ".jpg"
        dest = settings.storage_root / f"q_{int(time.time() * 1000)}_{src.stem}{suffix}"
        shutil.copy2(src, dest)
        target = dest.resolve()

    digest = sha256_file(target)
    conn = queue_db.connect(settings.queue_db_path)
    try:
        queue_db.init_schema(conn)
        inserted = queue_db.enqueue_violation(
            conn,
            camera_name=args.camera.strip(),
            violation_type=args.violation_type.strip(),
            file_path=target,
            file_sha256=digest,
        )
    finally:
        conn.close()

    out = {
        "ok": True,
        "enqueued": inserted,
        "deduplicated": not inserted,
        "file_path": str(target),
        "queue_db": str(settings.queue_db_path),
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
