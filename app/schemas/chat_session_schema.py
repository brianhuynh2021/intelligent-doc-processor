from datetime import datetime
from pydantic import BaseModel, Field


class ChatSessionCreate(BaseModel):
    name: str | None = None
    created_by_user_id: int | None = None


class ChatSessionResponse(BaseModel):
    id: int
    session_key: str
    name: str | None = None
    created_by_user_id: int | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ChatMessageResponse(BaseModel):
    id: int
    session_id: int
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True
