from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    expires_at: Optional[datetime] = None
    scopes: Optional[str] = Field(default=None, max_length=255)


class ApiKeyOut(BaseModel):
    id: int
    name: str
    key_prefix: str
    scopes: Optional[str] = None
    expires_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ApiKeyCreated(ApiKeyOut):
    plaintext_key: str = Field(
        description="Full key — shown ONCE on creation; store it somewhere safe."
    )
