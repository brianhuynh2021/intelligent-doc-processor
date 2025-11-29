from sqlalchemy import Boolean, Column, DateTime, Index, Integer, String, Text
from sqlalchemy.sql import func

from app.models.base import Base


class Document(Base):
    """Document model for file storage and processing"""

    default_status = "pending"

    __tablename__ = "documents"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)

    # File metadata
    name = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=False)
    content_type = Column(String(100), nullable=False)

    # Processing status & metrics
    status = Column(String(50), nullable=False, default=default_status)
    processing_step = Column(String(50), nullable=True)
    processing_progress = Column(Integer, nullable=False, default=0)
    processing_started_at = Column(DateTime(timezone=True))
    processing_completed_at = Column(DateTime(timezone=True))
    processing_duration_ms = Column(Integer, nullable=True)
    error_count = Column(Integer, default=0)
    last_error = Column(Text)

    # Extracted content
    text_content = Column(Text)

    # Ownership
    owner_id = Column(
        Integer, nullable=False, index=True, comment="References users.id"
    )

    # Soft delete
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime(timezone=True))

    download_count = Column(Integer, default=0)
    last_accessed_at = Column(DateTime(timezone=True))

    # Timestamps

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("idx_doc_owner_active_status", "owner_id", "is_deleted", "status"),
        Index("idx_doc_owner_active_created", "owner_id", "is_deleted", "created_at"),
        Index("idx_doc_active_status_created", "is_deleted", "status", "created_at"),
        # Admin/operations queries
        Index("idx_doc_content_type_size", "content_type", "file_size"),
        Index("idx_doc_processing_errors", "status", "error_count"),
        Index(
            "idx_doc_processing_time",
            "processing_started_at",
            "processing_completed_at",
        ),
        # Analytics queries
        Index("idx_doc_usage_metrics", "download_count", "last_accessed_at"),
        Index("idx_doc_deleted_cleanup", "is_deleted", "deleted_at"),
    )

    def __repr__(self):
        return f"<Document(id={self.id}, name='{self.name}', owner_id={self.owner_id}, status='{self.status}', deleted={self.is_deleted})>"
