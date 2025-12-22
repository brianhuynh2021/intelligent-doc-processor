from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DocumentStatusBuckets(BaseModel):
    pending: int = 0
    processing: int = 0
    completed: int = 0
    error: int = 0


class DocumentStatsResponse(BaseModel):
    total: int = 0
    by_status: DocumentStatusBuckets = Field(default_factory=DocumentStatusBuckets)
    by_content_type: dict[str, int] = Field(default_factory=dict)
    updated_last_24h: int = 0


class ChatStatsResponse(BaseModel):
    total_sessions: int = 0
    total_messages: int = 0
    messages_last_24h: int = 0
    active_sessions_last_24h: int = 0


class AdminChatSessionOut(BaseModel):
    id: int
    session_key: str
    name: str | None = None
    created_by_user_id: int | None = None
    created_at: datetime
    updated_at: datetime
    last_message_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
