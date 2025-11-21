# app/services/chunk_service.py
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
            char_start=start,
            char_end=end,
        )
        db.add(c)
        db_chunks.append(c)

    db.commit()
    for c in db_chunks:
        db.refresh(c)

    return [ChunkInDB.model_validate(c) for c in db_chunks]
