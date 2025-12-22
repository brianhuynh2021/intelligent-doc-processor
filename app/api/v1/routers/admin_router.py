from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import distinct, func
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.core.errors import ForbiddenError
from app.models.chat_message_model import ChatMessage
from app.models.chat_session_model import ChatSession
from app.models.document_model import Document
from app.schemas.admin_stats_schema import (
    AdminChatSessionOut,
    ChatStatsResponse,
    DocumentStatsResponse,
    DocumentStatusBuckets,
)

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_admin(current_user=Depends(get_current_user)):
    if not getattr(current_user, "is_admin", False):
        raise ForbiddenError("Admin access required")
    return current_user


def _apply_datetime_range(
    query, column, created_from: datetime | None, created_to: datetime | None
):
    if created_from is not None:
        query = query.filter(column >= created_from)
    if created_to is not None:
        query = query.filter(column <= created_to)
    return query


def _normalize_document_status(raw: str | None) -> str:
    s = (raw or "").strip().lower()
    if s in {"pending", "queued", "uploaded", "new"}:
        return "pending"
    if s in {
        "processing",
        "in_progress",
        "running",
        "ocr",
        "chunking",
        "ingesting",
        "embedding",
    }:
        return "processing"
    if s in {"completed", "done", "success"}:
        return "completed"
    if s in {"error", "failed", "failure"}:
        return "error"
    return "pending"


@router.get("/stats/documents", response_model=DocumentStatsResponse)
def documents_stats(
    created_from: datetime
    | None = Query(None, description="Filter by documents.created_at >= created_from"),
    created_to: datetime
    | None = Query(None, description="Filter by documents.created_at <= created_to"),
    db: Session = Depends(get_db),
    _admin=Depends(_require_admin),
):
    base = db.query(Document).filter(Document.is_deleted.is_(False))
    base = _apply_datetime_range(base, Document.created_at, created_from, created_to)

    total = int(base.with_entities(func.count(Document.id)).scalar() or 0)

    by_status = DocumentStatusBuckets()
    status_rows = (
        base.with_entities(Document.status, func.count(Document.id))
        .group_by(Document.status)
        .all()
    )
    for raw_status, count in status_rows:
        bucket = _normalize_document_status(raw_status)
        setattr(by_status, bucket, getattr(by_status, bucket) + int(count or 0))

    by_content_type_rows = (
        base.with_entities(Document.content_type, func.count(Document.id))
        .group_by(Document.content_type)
        .all()
    )
    by_content_type = {
        str(ct): int(count or 0) for ct, count in by_content_type_rows if ct
    }

    now = datetime.now(timezone.utc)
    window_start = now - timedelta(hours=24)
    updated_last_24h = int(
        base.filter(Document.updated_at >= window_start)
        .with_entities(func.count(Document.id))
        .scalar()
        or 0
    )

    return DocumentStatsResponse(
        total=total,
        by_status=by_status,
        by_content_type=by_content_type,
        updated_last_24h=updated_last_24h,
    )


@router.get("/stats/chat", response_model=ChatStatsResponse)
def chat_stats(
    created_from: datetime
    | None = Query(None, description="Filter by created_at >= created_from"),
    created_to: datetime
    | None = Query(None, description="Filter by created_at <= created_to"),
    db: Session = Depends(get_db),
    _admin=Depends(_require_admin),
):
    session_q = _apply_datetime_range(
        db.query(ChatSession), ChatSession.created_at, created_from, created_to
    )
    total_sessions = int(
        session_q.with_entities(func.count(ChatSession.id)).scalar() or 0
    )

    message_q = _apply_datetime_range(
        db.query(ChatMessage), ChatMessage.created_at, created_from, created_to
    )
    total_messages = int(
        message_q.with_entities(func.count(ChatMessage.id)).scalar() or 0
    )

    now = datetime.now(timezone.utc)
    window_start = now - timedelta(hours=24)
    if created_from is not None and created_from > window_start:
        window_start = created_from

    last_24h_q = db.query(ChatMessage).filter(ChatMessage.created_at >= window_start)
    if created_to is not None:
        last_24h_q = last_24h_q.filter(ChatMessage.created_at <= created_to)

    messages_last_24h = int(
        last_24h_q.with_entities(func.count(ChatMessage.id)).scalar() or 0
    )
    active_sessions_last_24h = int(
        last_24h_q.with_entities(func.count(distinct(ChatMessage.session_id))).scalar()
        or 0
    )

    return ChatStatsResponse(
        total_sessions=total_sessions,
        total_messages=total_messages,
        messages_last_24h=messages_last_24h,
        active_sessions_last_24h=active_sessions_last_24h,
    )


@router.get("/chat/sessions", response_model=list[AdminChatSessionOut])
def list_chat_sessions(
    limit: int = Query(20, ge=1, le=100),
    created_from: datetime
    | None = Query(None, description="Filter by sessions.created_at >= created_from"),
    created_to: datetime
    | None = Query(None, description="Filter by sessions.created_at <= created_to"),
    db: Session = Depends(get_db),
    _admin=Depends(_require_admin),
):
    last_msg_subq = (
        db.query(
            ChatMessage.session_id.label("session_id"),
            func.max(ChatMessage.created_at).label("last_message_at"),
        )
        .group_by(ChatMessage.session_id)
        .subquery()
    )

    q = db.query(ChatSession, last_msg_subq.c.last_message_at).outerjoin(
        last_msg_subq, ChatSession.id == last_msg_subq.c.session_id
    )
    q = _apply_datetime_range(q, ChatSession.created_at, created_from, created_to)
    q = q.order_by(
        func.coalesce(last_msg_subq.c.last_message_at, ChatSession.created_at).desc()
    )
    rows = q.limit(limit).all()

    return [
        AdminChatSessionOut(
            id=s.id,
            session_key=s.session_key,
            name=s.name,
            created_by_user_id=s.created_by_user_id,
            created_at=s.created_at,
            updated_at=s.updated_at,
            last_message_at=last_message_at,
        )
        for s, last_message_at in rows
    ]
