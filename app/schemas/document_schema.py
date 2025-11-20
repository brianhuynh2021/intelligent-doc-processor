from datetime import datetime

from pydantic import BaseModel


class DocumentBase(BaseModel):
    name: str
    original_filename: str
    file_path: str
    file_size: int
    content_type: str
    owner_id: int


class DocumentCreate(DocumentBase):
    pass


class DocumentInDB(DocumentBase):
    id: int
    status: str
    text_content: str | None = None
    processing_started_at: datetime | None = None
    processing_completed_at: datetime | None = None
    error_count: int
    last_error: str | None = None
    download_count: int
    last_accessed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    is_deleted: bool
    deleted_at: datetime | None = None

    class Config:
        from_attributes = True
