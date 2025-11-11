from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.user_model import User
from app.schemas.auth_schema import UserCreate


def create_user(db: Session, user_in: UserCreate):
    raw = getattr(user_in.password, "get_secret_value", lambda: user_in.password)()
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8")

    # choose a username
    base = (user_in.username or user_in.email.split("@")[0]).strip()
    if not base:
        base = "user"

    # ensure unique if username has a UNIQUE constraint
    candidate = base
    i = 0  # ensure import exists at top if not
    while db.query(User).filter(User.username == candidate).first():
        i += 1
        candidate = f"{base}{i}"

    user = User(
        email=user_in.email,
        username=candidate,  # <-- set username
        hashed_password=get_password_hash(raw),  # keep your current hasher
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user_by_email(db: Session, email: str):
    return db.query(User).filter(User.email == email).first()


def get_user_by_username(db: Session, username: str):
    return db.query(User).filter(User.username == username).first()


def get_user_by_login(db: Session, identifier: str):
    if "@" in identifier:
        return get_user_by_email(db, identifier)
    return get_user_by_username(db, identifier)
