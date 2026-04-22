import sys
import traceback
from pathlib import Path

from fastapi import APIRouter, Form, Request, status
from fastapi.responses import RedirectResponse

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import verify_password
from app.core.urls import app_url
from app.models import User
from app.templating import templates

router = APIRouter(tags=["auth"])

_PROJECT_DIR = Path(__file__).resolve().parent.parent.parent


def _append_login_traceback_to_file() -> None:
    text = traceback.format_exc() + "\n" + "-" * 60 + "\n"
    sys.stderr.write(text)
    targets = [
        _PROJECT_DIR / "login_error.log",
        Path("/tmp/qrpass_login_error.log"),
    ]
    for log_file in targets:
        try:
            with log_file.open("a", encoding="utf-8") as fp:
                fp.write(text)
            return
        except OSError:
            continue


@router.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {"error": None})


@router.post("/login")
def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    # Сессию БД открываем внутри try: иначе ошибка SQLite/пути из Depends(get_db)
    # не попадает в except и login_error.log не создаётся.
    db = None
    try:
        db = SessionLocal()
        user = db.query(User).filter(User.username == username).first()
        if not user or not verify_password(password, user.hashed_password):
            return templates.TemplateResponse(
                request,
                "login.html",
                {"error": "Неверный логин или пароль"},
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        request.session["user_id"] = user.id
        return RedirectResponse(url=app_url("/dashboard"), status_code=status.HTTP_303_SEE_OTHER)
    except Exception as exc:
        traceback.print_exc()
        _append_login_traceback_to_file()
        msg = (
            "Ошибка при входе. Смотрите файл `login_error.log` в каталоге приложения "
            "или `/tmp/qrpass_login_error.log`. Либо в `.env`: SHOW_LOGIN_ERRORS=true."
        )
        if settings.show_login_errors:
            msg = f"Ошибка: {exc!r}. См. login_error.log или /tmp/qrpass_login_error.log"
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": msg},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    finally:
        if db is not None:
            db.close()


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url=app_url("/login"), status_code=status.HTTP_303_SEE_OTHER)
