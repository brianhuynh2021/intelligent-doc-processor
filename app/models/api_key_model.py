from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.sql import func

from app.models.base import Base


class ApiKey(Base):
    """Long-lived API key for programmatic access.

    Storage: hash of the full key (bcrypt/pbkdf2). The plaintext key is shown
    to the user exactly once on creation. The `key_prefix` is the first 12
    chars of the key (incl. `dpk_`) and is used to look up the row before
    verifying the hash — a constant-time check would scan all rows otherwise.
    """

    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String(100), nullable=False)
    key_prefix = Column(String(16), nullable=False, index=True)
    key_hash = Column(String(255), nullable=False)
    scopes = Column(String(255), nullable=True)

    expires_at = Column(DateTime(timezone=True), nullable=True)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True, index=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (Index("idx_api_keys_user_active", "user_id", "revoked_at"),)

    def __repr__(self) -> str:
        return (
            f"<ApiKey(id={self.id}, user_id={self.user_id}, prefix={self.key_prefix})>"
        )
