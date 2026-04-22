"""
Оставить в таблице violations одну запись (самую новую по timestamp), остальное удалить.
Запуск из каталога qrpass_web:
  python scripts/prune_violations_keep_one.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Корень проекта: scripts/ -> qrpass_web/
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

os.chdir(_ROOT)

from sqlalchemy import create_engine, text  # noqa: E402

from app.core.config import settings  # noqa: E402


def main() -> None:
    url = settings.database_url
    if not url.startswith("sqlite"):
        print("Скрипт рассчитан на SQLite; для другой БД выполните аналог вручную.")
        sys.exit(1)

    engine = create_engine(url, connect_args={"check_same_thread": False})
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT id FROM violations ORDER BY timestamp DESC LIMIT 1")
        ).fetchone()
        if not row:
            print("Таблица violations пуста — нечего удалять.")
            return
        keep_id = row[0]
        r = conn.execute(text("DELETE FROM violations WHERE id != :id"), {"id": keep_id})
        print(f"Оставлена запись id={keep_id}, удалено строк: {r.rowcount}.")


if __name__ == "__main__":
    main()
