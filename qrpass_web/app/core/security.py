from fastapi import Depends, HTTPException, Request, status
import bcrypt
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.urls import app_url
from app.models import User

# bcrypt принимает не больше 72 байт секрета (см. bcrypt.checkpw).
_BCRYPT_MAX_BYTES = 72


def _secret_bytes(password: str) -> bytes:
    return password.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def get_password_hash(password: str) -> str:
    secret = _secret_bytes(password)
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(secret, salt).decode("ascii")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not hashed_password:
        return False
    secret = _secret_bytes(plain_password)
    try:
        h = (
            hashed_password.encode("ascii")
            if isinstance(hashed_password, str)
            else hashed_password
        )
        return bcrypt.checkpw(secret, h)
    except (ValueError, TypeError):
        return False


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": app_url("/login")},
        )
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        request.session.clear()
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": app_url("/login")},
        )
    return user
