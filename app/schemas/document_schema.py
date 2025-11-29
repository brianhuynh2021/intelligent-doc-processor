from datetime import datetime
from typing import List

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
    processing_step: str | None = None
    processing_progress: int
    text_content: str | None = None
    processing_started_at: datetime | None = None
    processing_completed_at: datetime | None = None
    processing_duration_ms: int | None = None
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


class IngestionStep(BaseModel):
    name: str
    duration_ms: int
    detail: str | None = None


class IngestionResponse(BaseModel):
    document: DocumentInDB
    total_duration_ms: int
    chunks_indexed: int
    steps: List[IngestionStep]
