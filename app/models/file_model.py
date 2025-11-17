from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.sql import func

from app.models.base import Base


class File(Base):
    """File model for storing uploaded document metadata"""

    __tablename__ = "files"

    # Integer ID for performance (internal use)
    id = Column(Integer, primary_key=True, index=True)

    # Business ID (UUID dùng trong API, không lộ id nội bộ)
    file_id = Column(String(36), unique=True, nullable=False, index=True)

    # Original filename client upload
    filename = Column(String(255), nullable=False)

    # Actual stored filename on disk / MinIO (thường là uuid.ext)
    stored_name = Column(String(255), nullable=False)

    # MIME type: application/pdf, text/plain, image/png, ...
    content_type = Column(String(100), nullable=False)

    # File size in bytes
    size = Column(BigInteger, nullable=False)

    # Path lưu file (local path hoặc object key trên MinIO/S3)
    path = Column(String(500), nullable=False)

    # Optional: user upload (nếu muốn tracking)
    uploaded_by_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Soft delete (giống User)
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime(timezone=True))

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Performance indexes
    __table_args__ = (
        # Truy vấn file còn sống theo file_id
        Index("idx_files_file_id_active", "file_id", "is_deleted"),
        # Truy vấn theo user
        Index("idx_files_uploaded_by_user", "uploaded_by_user_id", "is_deleted"),
        # Cleanup job xoá mềm
        Index("idx_files_deleted_cleanup", "is_deleted", "deleted_at"),
        # Lọc theo loại file (pdf, image, ...)
        Index("idx_files_content_type", "content_type"),
    )

    def __repr__(self):
        return (
            f"<File(id={self.id}, file_id='{self.file_id}', "
            f"filename='{self.filename}', content_type='{self.content_type}')>"
        )
