import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import app_config
from app.core.database import get_db
from app.core.security import create_access_token, verify_password
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.user_repository import (
    create_user,
    get_user_by_email,
    get_user_by_login,
)
from app.schemas.auth_schema import LoginRequest, UserCreate, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


def _issue_tokens(
    db: Session, *, user_id: int, subject: str, request: Request | None = None
):
    user_agent = request.headers.get("User-Agent") if request else None
    ip = request.client.host if request and request.client else None

    access_token = create_access_token(subject=subject, extra={"scope": "user:read"})

    raw_token = secrets.token_urlsafe(64)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)

    RefreshTokenRepository.create(
        db=db,
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_at,
        user_agent=user_agent,
        ip=ip,
    )

    return {
        "access_token": access_token,
        "refresh_token": raw_token,
        "token_type": "bearer",
        "expires_in": app_config.ACCESS_TOKEN_EXPIRE_MINUTES,
    }


def _do_login(
    db: Session, identifier: str, password: str, request: Request | None = None
):
    # identifier có thể là email hoặc username
    user = get_user_by_login(db, identifier)
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )
    return _issue_tokens(db, user_id=user.id, subject=user.email, request=request)


@router.post("/login")
def login(
    request: Request,
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    return _do_login(
        db, identifier=form.username, password=form.password, request=request
    )


@router.post("/login-json")
def login_json(body: LoginRequest, request: Request, db: Session = Depends(get_db)):
    return _do_login(db, identifier=body.email, password=body.password, request=request)


@router.post("/register", response_model=UserOut, summary="Register a new user")
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    existing_user = get_user_by_email(db, email=user_in.email)
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = create_user(db, user_in)
    return user


class RefreshIn(BaseModel):
    refresh_token: str


@router.post("/refresh")
def refresh(body: RefreshIn, request: Request, db: Session = Depends(get_db)):
    token_hash = hashlib.sha256(body.refresh_token.encode()).hexdigest()
    stored = RefreshTokenRepository.get_valid(db, token_hash)
    if not stored:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    # Rotate the old refresh token
    RefreshTokenRepository.revoke(db, token_hash)

    # Issue a new pair (use user_id; subject can be user email if you prefer to load it)
    return _issue_tokens(
        db, user_id=stored.user_id, subject=str(stored.user_id), request=request
    )
