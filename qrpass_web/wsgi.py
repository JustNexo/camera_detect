import os
import sys
import traceback

# На части shared-хостингов при импорте из .pyc встречается OSError: [Errno 14] Bad address
# (битый кэш/NFS). Не писать байткод при работе через WSGI — снижает риск.
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
sys.dont_write_bytecode = True

# 1. Устанавливаем правильную рабочую директорию
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)

# Маркер для диагностики: если файла нет — выполняется не этот wsgi или падает до записи.
try:
    with open("/tmp/qrpass_wsgi_boot.txt", "w", encoding="utf-8") as _boot:
        _boot.write(f"ROOT={ROOT}\ncwd={os.getcwd()}\n")
except OSError:
    pass

# 2. Вручную подключаем venv (критично для Sprinthost uWSGI)
site_packages: str | None = None
VENV_DIR = os.path.join(ROOT, "venv")
if os.path.exists(VENV_DIR):
    import site

    py_version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    for lib in ("lib", "lib64"):
        p = os.path.join(VENV_DIR, lib, py_version, "site-packages")
        if os.path.isdir(p):
            site_packages = p
            site.addsitedir(site_packages)
            break

# 3. Пытаемся запустить приложение. Если падает - выводим ошибку в браузер!
try:
    from a2wsgi import ASGIMiddleware
    from app.main import app
    application = ASGIMiddleware(app)
except Exception as e:
    error_tb = traceback.format_exc()
    
    def application(environ, start_response):
        status = '500 Internal Server Error'
        headers = [('Content-type', 'text/plain; charset=utf-8')]
        start_response(status, headers)
        
        debug_info = (
            f"WSGI INIT ERROR:\n"
            f"----------------\n"
            f"{error_tb}\n"
            f"----------------\n"
            f"Python version: {sys.version}\n"
            f"Current dir: {os.getcwd()}\n"
            f"Venv site-packages: {site_packages!r} exists={site_packages is not None and os.path.isdir(site_packages)}\n"
            f"sys.path[0:3]: {sys.path[:3]!r}"
        )
        return [debug_info.encode('utf-8')]
