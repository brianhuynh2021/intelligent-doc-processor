from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base


class RefreshToken(Base):
    """Refresh token store (opaque token hashed, rotates, revocable)"""

    __tablename__ = "refresh_tokens"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)

    # Ownership
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="FK to users.id",
    )

    # Opaque token hash (never store raw token)
    token_hash = Column(String(255), nullable=False, unique=True, index=True)

    # Lifetime / revocation
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True))

    # Observability (optional)
    user_agent = Column(String(255))
    ip = Column(String(64))

    # Soft delete (keeping the same pattern as Document)
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime(timezone=True))

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

    # Relationship
    user = relationship("User", backref="refresh_tokens", passive_deletes=True)

    __table_args__ = (
        # Common lookups
        Index(
            "idx_rt_user_active",
            "user_id",
            "expires_at",
            "revoked_at",
            "is_deleted",
        ),
        # Safety/consistency
        UniqueConstraint("token_hash", name="uq_rt_token_hash"),
        CheckConstraint("expires_at IS NOT NULL", name="ck_rt_expires_not_null"),
    )

    def __repr__(self):
        return (
            f"<RefreshToken(id={self.id}, user_id={self.user_id}, "
            f"revoked_at={self.revoked_at}, expires_at={self.expires_at}, "
            f"deleted={self.is_deleted})>"
        )
