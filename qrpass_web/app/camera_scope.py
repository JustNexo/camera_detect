"""Составной ключ «объект (площадка) + камера» для состояния в памяти и URL потока."""
from __future__ import annotations

import json
from typing import Any

# Если клиент не передал site_name — показываем так (и не смешиваем с явным названием).
DEFAULT_SITE_LABEL = "Без объекта"


def scope_key(site: str | None, camera: str) -> str:
    s = (site or "").strip() or DEFAULT_SITE_LABEL
    return json.dumps({"site": s, "camera": camera}, ensure_ascii=False, sort_keys=True)


def parse_scope_key(key: str) -> tuple[str, str]:
    try:
        obj: Any = json.loads(key)
        if isinstance(obj, dict) and "site" in obj and "camera" in obj:
            return str(obj["site"]), str(obj["camera"])
    except (json.JSONDecodeError, TypeError, KeyError):
        pass
    return DEFAULT_SITE_LABEL, key


def normalize_site_for_display(site: str) -> str:
    s = (site or "").strip()
    return s or DEFAULT_SITE_LABEL
