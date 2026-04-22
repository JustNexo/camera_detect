import argparse
import sys
from pathlib import Path

# Добавляем корень проекта в PYTHONPATH, чтобы импорты app.* работали
# при запуске скрипта как: python scripts/create_admin.py
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.database import Base, SessionLocal, engine
from app.core.security import get_password_hash
from app.models import User


def main() -> None:
    parser = argparse.ArgumentParser(description="Создание администратора QRPass")
    parser.add_argument("--username", required=True, help="Логин")
    parser.add_argument("--password", required=True, help="Пароль")
    args = parser.parse_args()

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        exists = db.query(User).filter(User.username == args.username).first()
        if exists:
            print(f"Пользователь '{args.username}' уже существует.")
            return
        user = User(username=args.username, hashed_password=get_password_hash(args.password))
        db.add(user)
        db.commit()
        print(f"Пользователь '{args.username}' создан.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
