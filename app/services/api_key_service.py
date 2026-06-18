from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.security import get_password_hash, verify_password
from app.models.api_key_model import ApiKey
from app.models.user_model import User

KEY_PLAINTEXT_PREFIX = "dpk_"  # doc-processor key
PREFIX_DB_LEN = 12  # "dpk_" + 8 random chars stored for lookup
RAW_BYTES = 32  # 256-bit token


def _generate_plaintext() -> tuple[str, str]:
    """Returns (full_plaintext_key, db_prefix)."""
    token = secrets.token_urlsafe(RAW_BYTES)
    full = f"{KEY_PLAINTEXT_PREFIX}{token}"
    return full, full[:PREFIX_DB_LEN]


def create_api_key(
    db: Session,
    user: User,
    name: str,
    expires_at: Optional[datetime] = None,
    scopes: Optional[str] = None,
) -> tuple[ApiKey, str]:
    """Create and persist an API key. Returns (db_row, plaintext_key).

    The plaintext is returned ONCE — caller must show it to the user and
    not log/store it.
    """
    plaintext, prefix = _generate_plaintext()
    row = ApiKey(
        user_id=user.id,
        name=name,
        key_prefix=prefix,
        key_hash=get_password_hash(plaintext),
        scopes=scopes,
        expires_at=expires_at,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row, plaintext


def list_user_api_keys(db: Session, user: User) -> list[ApiKey]:
    return (
        db.query(ApiKey)
        .filter(ApiKey.user_id == user.id)
        .order_by(ApiKey.created_at.desc())
        .all()
    )


def revoke_api_key(db: Session, user: User, key_id: int) -> bool:
    row = (
        db.query(ApiKey).filter(ApiKey.id == key_id, ApiKey.user_id == user.id).first()
    )
    if not row or row.revoked_at is not None:
        return False
    row.revoked_at = datetime.now(timezone.utc)
    db.commit()
    return True


def resolve_api_key(db: Session, plaintext: str) -> Optional[User]:
    """Look up the owning user for a plaintext key. Returns None if invalid,
    revoked, or expired. Also touches last_used_at on success.
    """
    if not plaintext or not plaintext.startswith(KEY_PLAINTEXT_PREFIX):
        return None
    prefix = plaintext[:PREFIX_DB_LEN]
    candidates = (
        db.query(ApiKey)
        .filter(ApiKey.key_prefix == prefix, ApiKey.revoked_at.is_(None))
        .all()
    )
    now = datetime.now(timezone.utc)
    for row in candidates:
        if row.expires_at is not None and row.expires_at < now:
            continue
        if verify_password(plaintext, row.key_hash):
            row.last_used_at = now
            db.commit()
            user = db.query(User).filter(User.id == row.user_id).first()
            if not user or not user.is_active:
                return None
            return user
    return None
