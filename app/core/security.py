# app/core/security.py
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from jose import jwt
from passlib.context import CryptContext

from app.core.config import app_config

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(
    subject: str | int,
    expires_minutes: Optional[int] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Create a JWT access token that follows OAuth2 / OIDC conventions.

    Adds standard claims:
      - sub: subject (user ID or email)
      - iat: issued at
      - nbf: not before
      - exp: expiration
      - iss: issuer (your app/service)
      - aud: audience (intended clients)
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(
        minutes=expires_minutes or app_config.ACCESS_TOKEN_EXPIRE_MINUTES
    )

    payload: Dict[str, Any] = {
        "sub": str(subject),
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "iss": "intelligent-doc-processor",
        "aud": "intelligent-doc-client",
    }
    if extra:
        payload.update(extra)

    return jwt.encode(
        payload, app_config.JWT_SECRET_KEY, algorithm=app_config.JWT_ALGORITHM
    )


def decode_token(token: str) -> dict:
    return jwt.decode(
        token, app_config.JWT_SECRET_KEY, algorithms=[app_config.JWT_ALGORITHM]
    )
