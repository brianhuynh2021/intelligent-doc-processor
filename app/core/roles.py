from __future__ import annotations

from enum import Enum


class UserRole(str, Enum):
    """User roles, in ascending privilege order."""

    VIEWER = "viewer"
    USER = "user"
    ADMIN = "admin"


ROLE_RANK = {
    UserRole.VIEWER: 0,
    UserRole.USER: 10,
    UserRole.ADMIN: 100,
}


def role_at_least(role: str | UserRole, minimum: UserRole) -> bool:
    try:
        r = UserRole(role) if isinstance(role, str) else role
    except ValueError:
        return False
    return ROLE_RANK[r] >= ROLE_RANK[minimum]
