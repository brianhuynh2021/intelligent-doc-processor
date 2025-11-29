import uuid
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.chat_message_model import ChatMessage
from app.models.chat_session_model import ChatSession


def create_session(db: Session, name: str | None = None, created_by_user_id: int | None = None) -> ChatSession:
    session = ChatSession(
        session_key=str(uuid.uuid4()),
        name=name,
        created_by_user_id=created_by_user_id,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_session_by_id(db: Session, session_id: int) -> Optional[ChatSession]:
    return db.query(ChatSession).filter(ChatSession.id == session_id).first()


def get_session_by_key(db: Session, session_key: str) -> Optional[ChatSession]:
    return db.query(ChatSession).filter(ChatSession.session_key == session_key).first()


def add_message(db: Session, session_id: int, role: str, content: str) -> ChatMessage:
    msg = ChatMessage(session_id=session_id, role=role, content=content)
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


def get_messages(db: Session, session_id: int, limit: int = 20) -> List[ChatMessage]:
    return (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
        .all()
    )[::-1]  # return ascending order
