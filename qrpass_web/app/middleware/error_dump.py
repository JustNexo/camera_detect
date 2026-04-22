"""
Перехват любых исключений при обработке запроса и запись traceback в файлы.
Нужен на shared-хостинге, когда Depends/сессия падают до входа в обработчик роутов.
"""
import os
import traceback
from pathlib import Path

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.config import settings


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _log_targets() -> list[Path]:
    extra: list[Path] = []
    if getattr(settings, "error_log_dir", None):
        d = settings.error_log_dir.strip()
        if d:
            extra.append(Path(d) / "qrpass_last_error.log")
    home = Path(os.path.expanduser("~"))
    return extra + [
        _project_root() / "qrpass_last_error.log",
        Path("/tmp/qrpass_last_error.log"),
        home / "qrpass_last_error.log",
    ]


def dump_exception_to_files(request: Request, exc: BaseException) -> None:
    lines = [
        f"URL: {request.method} {request.url}",
        f"Path: {request.url.path}",
        "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
        "-" * 72 + "\n",
    ]
    text = "\n".join(lines)

    for path in _log_targets():
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fp:
                fp.write(text)
        except OSError:
            continue


class DumpErrorsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except BaseException as exc:
            dump_exception_to_files(request, exc)
            raise


def write_startup_probe() -> None:
    """Проверка, куда вообще можно писать с правами веб-процесса."""
    msg = f"ok cwd={os.getcwd()} home={os.path.expanduser('~')}\n"
    extra_probe: list[Path] = []
    if getattr(settings, "error_log_dir", None) and settings.error_log_dir.strip():
        extra_probe.append(Path(settings.error_log_dir.strip()) / "qrpass_write_probe.txt")
    paths = extra_probe + [
        _project_root() / "qrpass_write_probe.txt",
        Path("/tmp/qrpass_write_probe.txt"),
        Path(os.path.expanduser("~")) / "qrpass_write_probe.txt",
    ]
    for path in paths:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8") as fp:
                fp.write(msg)
        except OSError:
            continue
