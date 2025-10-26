from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.sql import func

from app.models.base import Base


class Chunk(Base):
    """
    Chunk model for RAG - NO FK for consistency and scalability.
    Application enforces integrity through service layer.
    """

    __tablename__ = "chunks"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(
        Integer, nullable=False, index=True, comment="Reference to documents.id "
    )

    document_owner_id = Column(
        Integer,
        nullable=False,
        index=True,
        comment="Denormalized owner_id for fast queries without joins",
    )
    # Content
    content = Column(Text, nullable=False)

    # Chunk metadata
    chunk_index = Column(Integer, nullable=False)
    page_number = Column(Integer, nullable=True)

    # Embeddings
    embedding = Column(ARRAY(Float), nullable=True)
    embedding_model = Column(String(100), nullable=True)
    embedding_dim = Column(Integer, nullable=True)

    # Stats
    token_count = Column(Integer, nullable=True)
    char_count = Column(Integer, nullable=False, default=0)

    # Soft delete
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
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

    # Indexes - Consistent pattern with Document model
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="ux_chunk_doc_index"),
        # Most common query: get chunks by document (ordered)
        Index("idx_chunk_doc_active_index", "document_id", "is_deleted", "chunk_index"),
        # Query by owner without joining documents! (denormalized pattern)
        Index(
            "idx_chunk_owner_active_created",
            "document_owner_id",
            "is_deleted",
            "created_at",
        ),
        # Active chunks by creation time
        Index("idx_chunk_active_created", "is_deleted", "created_at"),
        # Cleanup deleted chunks
        Index("idx_chunk_deleted_cleanup", "is_deleted", "deleted_at"),
        # Page-based retrieval
        Index("idx_chunk_doc_page", "document_id", "page_number", "chunk_index"),
    )

    def __repr__(self):
        """String representation - consistent with Document"""
        return (
            f"<Chunk("
            f"id={self.id}, "
            f"doc_id={self.document_id}, "
            f"owner_id={self.document_owner_id}, "
            f"index={self.chunk_index}, "
            f"chars={self.char_count}, "
            f"deleted={self.is_deleted}"
            f")>"
        )
