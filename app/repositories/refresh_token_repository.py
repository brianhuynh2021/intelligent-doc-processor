from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.refresh_token_model import RefreshToken


class RefreshTokenRepository:
    @staticmethod
    def create(
        db: Session,
        user_id: int,
        token_hash: str,
        expires_at: datetime,
        user_agent: str = None,
        ip: str = None,
    ):
        rt = RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            user_agent=user_agent,
            ip=ip,
        )
        db.add(rt)
        db.commit()
        db.refresh(rt)
        return rt

    @staticmethod
    def get_valid(db: Session, token_hash: str):
        return (
            db.query(RefreshToken)
            .filter(
                RefreshToken.token_hash == token_hash,
                RefreshToken.is_deleted.is_(False),
                RefreshToken.revoked_at.is_(None),
                RefreshToken.expires_at > datetime.now(timezone.utc),
            )
            .first()
        )

    @staticmethod
    def revoke(db: Session, token_hash: str):
        rt = (
            db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()
        )
        if rt:
            rt.revoked_at = datetime.now(timezone.utc)
            db.commit()
        return rt
