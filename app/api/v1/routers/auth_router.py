from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import create_access_token, verify_password
from app.repositories.user_repository import (
    create_user,
    get_user_by_email,
    get_user_by_login,
)
from app.schemas.auth_schema import LoginRequest, UserCreate, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


def _do_login(db: Session, identifier: str, password: str):
    # identifier có thể là email hoặc username
    user = get_user_by_login(db, identifier)
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )
    access_token = create_access_token(subject=user.email, extra={"scope": "user:read"})
    return {"access_token": access_token, "token_type": "bearer", "expires_in": 1800}


@router.post("/login")
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    return _do_login(db, identifier=form.username, password=form.password)


@router.post("/login-json")
def login_json(body: LoginRequest, db: Session = Depends(get_db)):
    return _do_login(db, identifier=body.email, password=body.password)


@router.post("/register", response_model=UserOut, summary="Register a new user")
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    existing_user = get_user_by_email(db, email=user_in.email)
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = create_user(db, user_in)
    return user
