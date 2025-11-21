# app/schemas/files.py
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

# ===== Response cho endpoint upload hiện tại =====


class UploadedFileResponse(BaseModel):
    file_id: str
    filename: str
    content_type: str
    size: int
    url: str | None = None
    document_id: Optional[int] = None


# ===== Schema cho DB layer =====


class FileBase(BaseModel):
    filename: str
    content_type: str
    size: int


class FileCreate(FileBase):
    file_id: str  # uuid sinh ra khi upload
    stored_name: str  # tên thực tế lưu (uuid.ext)
    path: str  # đường dẫn lưu file


class FileInDB(FileBase):
    id: int
    file_id: str
    stored_name: str
    path: str
    created_at: datetime
    updated_at: datetime | None = None
    is_deleted: bool

    class Config:
        from_attributes = True  # cho phép .model_validate(obj SQLAlchemy)


# ===== List files =====


class FileListItem(FileInDB):
    pass


class FileListResponse(BaseModel):
    items: list[FileListItem]
    total: int


# ===== Download metadata =====


class FileDownloadResponse(FileInDB):
    url: str | None = None


# ===== Delete response =====


class FileDeleteResponse(BaseModel):
    file_id: str
    deleted: bool
    message: str = "File deleted successfully"
