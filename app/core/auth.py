from typing import Callable, Optional

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.roles import UserRole, role_at_least
from app.core.security import decode_token
from app.models.user_model import User

# Optional so a request authenticating only with X-API-Key (no Authorization
# header) still reaches our handler instead of being rejected by the scheme.
auth_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(auth_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Authenticate via either a JWT (``Authorization: Bearer <jwt>``) or an
    API key (``X-API-Key: dpk_...``, or the key as a bearer token). Returns the
    owning :class:`User`."""
    from app.services.api_key_service import resolve_api_key

    cred_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # 1) API key via X-API-Key header
    if x_api_key:
        user = resolve_api_key(db, x_api_key)
        if user:
            return user
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked API key",
        )

    # 2) Authorization: Bearer — either a dpk_ API key or a JWT
    if credentials and credentials.scheme.lower() == "bearer":
        token = credentials.credentials
        if token.startswith("dpk_"):
            user = resolve_api_key(db, token)
            if user:
                return user
            raise cred_exc
        try:
            payload = decode_token(token)
            sub: str | None = payload.get("sub")
            if sub is None:
                raise cred_exc
        except JWTError:
            raise cred_exc
        user = db.query(User).filter(User.id == int(sub)).first()
        if not user or not user.is_active:
            raise cred_exc
        return user

    raise cred_exc


# Backward-compatible alias: API-key support is now built into get_current_user.
get_current_user_or_api_key = get_current_user


def require_role(minimum: UserRole) -> Callable[..., User]:
    """Dependency factory: ensures current user has at least `minimum` role."""

    def _dep(current_user: User = Depends(get_current_user)) -> User:
        user_role = getattr(current_user, "role", None) or (
            "admin" if getattr(current_user, "is_admin", False) else "user"
        )
        if not role_at_least(user_role, minimum):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role: {minimum.value} or higher",
            )
        return current_user

    return _dep
