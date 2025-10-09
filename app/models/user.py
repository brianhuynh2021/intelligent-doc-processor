from sqlalchemy import Boolean, Column, DateTime, Index, Integer, String
from sqlalchemy.sql import func

from app.models.base import Base


class User(Base):
    """User model for authentication and authorization"""

    __tablename__ = "users"

    # Integer ID for performance (internal use)
    id = Column(Integer, primary_key=True, index=True)

    # Authentication fields
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)

    # User status
    is_active = Column(Boolean, default=True, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)

    # Soft delete (never hard delete)
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime(timezone=True))

    # User activity tracking
    last_login_at = Column(DateTime(timezone=True))
    login_count = Column(Integer, default=0)
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

    # Performance indexes
    __table_args__ = (
        Index("idx_user_email_active_deleted", "email", "is_active", "is_deleted"),
        Index(
            "idx_user_username_active_deleted", "username", "is_active", "is_deleted"
        ),
        Index("idx_user_deleted_cleanup", "is_deleted", "deleted_at"),
        Index("idx_user_activity_tracking", "login_count", "last_login_at"),
    )

    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}', username='{self.username}')>"
