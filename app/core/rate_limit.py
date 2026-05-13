from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings


def _limits(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


limiter = Limiter(
    key_func=get_remote_address,
    default_limits=_limits(settings.RATE_LIMIT_DEFAULT),
    storage_uri=settings.RATE_LIMIT_STORAGE_URI,
    headers_enabled=False,
    enabled=settings.RATE_LIMIT_ENABLED,
)
