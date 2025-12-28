# app/services/chunk_service.py
from datetime import datetime, timezone
from typing import List

from sqlalchemy.orm import Session

from app.models.chunk_model import Chunk
from app.models.document_model import Document
from app.schemas.chunk_schema import ChunkInDB
from app.services.text_service import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    chunk_text,
)


def chunk_document(
    db: Session,
    document_id: int,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    *,
    update_status: bool = True,
) -> List[ChunkInDB]:
    doc = (
        db.query(Document)
        .filter(Document.id == document_id, Document.is_deleted == False)  # noqa: E712
        .first()
    )
    if not doc:
        raise ValueError("Document not found")

    if not doc.text_content:
        raise ValueError("Document has no text_content. Run OCR first.")

    started_at = None
    if update_status:
        started_at = datetime.now(timezone.utc)
        doc.processing_started_at = started_at
        doc.status = "processing"
        doc.processing_step = "chunk"
        doc.processing_progress = doc.processing_progress or 0
        doc.processing_completed_at = None
        doc.processing_duration_ms = None
        doc.last_error = None
        db.commit()
        db.refresh(doc)

    try:
        # Xoá chunks cũ
        db.query(Chunk).filter(Chunk.document_id == document_id).delete()
        db.flush()

        # Gọi text_service để chunk
        raw_chunks = chunk_text(
            doc.text_content,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

        db_chunks: list[Chunk] = []
        for idx, (content, start, end) in enumerate(raw_chunks):
            c = Chunk(
                document_id=document_id,
                document_owner_id=doc.owner_id,
                content=content,
                chunk_index=idx,
                page_number=None,
                char_count=len(content),
                token_count=None,
            )
            db.add(c)
            db_chunks.append(c)

        if update_status:
            doc.status = "processing"
            doc.processing_step = "chunk"
            doc.processing_progress = 70
            finished_at = datetime.now(timezone.utc)
            if started_at:
                doc.processing_duration_ms = int(
                    (finished_at - started_at).total_seconds() * 1000
                )

        db.commit()
        for c in db_chunks:
            db.refresh(c)
        db.refresh(doc)

        return [ChunkInDB.model_validate(c) for c in db_chunks]
    except Exception as exc:
        db.rollback()
        if update_status:
            doc.status = "error"
            doc.processing_step = "error"
            doc.processing_progress = doc.processing_progress or 0
            doc.processing_completed_at = datetime.now(timezone.utc)
            if started_at:
                doc.processing_duration_ms = int(
                    (doc.processing_completed_at - started_at).total_seconds() * 1000
                )
            doc.error_count = (doc.error_count or 0) + 1
            doc.last_error = str(exc)
            db.commit()
            db.refresh(doc)
        raise
