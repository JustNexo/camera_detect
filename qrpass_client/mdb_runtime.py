"""
Подключение к существующему mdb.py на объекте (SQLite users.db).

Варианты:
- Запуск из каталога, где лежат `mdb.py` и `users.db` рядом с клиентом.
- Или задайте MDB_PARENT_DIR — путь к каталогу со старыми скриптами (в sys.path).
- Или MDB_MODULE_FILE — полный путь к файлу mdb.py.

Обфускация PyArmor: рядом с `mdb.py` должен быть пакет `pyarmor_runtime_000000`
(часто в родительской папке). Перед загрузкой в sys.path добавляются каталог
с `mdb.py`, его родитель и опционально PYARMOR_RUNTIME_DIR.
"""
from __future__ import annotations

import importlib
import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType


def expanded_path(p: str) -> str:
    return os.path.expandvars(os.path.expanduser(p))


def _prepend_sys_path_unique(path: Path) -> None:
    s = str(path.resolve())
    if s not in sys.path:
        sys.path.insert(0, s)


def _prepend_paths_for_pyarmor(mdb_py: Path) -> None:
    """Чтобы `import pyarmor_runtime_000000` из обфусцированного mdb сработал."""
    rt = (os.getenv("PYARMOR_RUNTIME_DIR") or "").strip()
    if rt:
        p = Path(expanded_path(rt)).resolve()
        if p.is_dir():
            _prepend_sys_path_unique(p)
    d = mdb_py.resolve().parent
    _prepend_sys_path_unique(d)
    parent = d.parent
    if parent != d:
        _prepend_sys_path_unique(parent)


def load_mdb_module() -> ModuleType:
    rt = (os.getenv("PYARMOR_RUNTIME_DIR") or "").strip()
    if rt:
        p = Path(expanded_path(rt)).resolve()
        if p.is_dir():
            _prepend_sys_path_unique(p)

    parent = (os.getenv("MDB_PARENT_DIR") or "").strip()
    if parent:
        p = Path(parent).resolve()
        if p.is_dir() and str(p) not in sys.path:
            sys.path.insert(0, str(p))

    explicit = (os.getenv("MDB_MODULE_FILE") or "").strip()
    if explicit:
        path = Path(expanded_path(explicit)).resolve()
    else:
        path = Path("mdb.py").resolve()

    if path.is_file():
        _prepend_paths_for_pyarmor(path)
        spec = importlib.util.spec_from_file_location("mdb", path)
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            sys.modules["mdb"] = mod
            spec.loader.exec_module(mod)
            return mod

    try:
        return importlib.import_module("mdb")
    except ImportError as exc:
        raise ImportError(
            "Не найден mdb.py. Задайте MDB_PARENT_DIR или MDB_MODULE_FILE, "
            "либо положите mdb.py рядом с клиентом (см. DEPLOY_OBJECT.md)."
        ) from exc


def ensure_database(mdb: ModuleType) -> None:
    fn = getattr(mdb, "create_database", None)
    if callable(fn):
        fn()
