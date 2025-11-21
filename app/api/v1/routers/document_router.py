from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.document_model import Document
from app.schemas.chunk_schema import ChunkInDB
from app.schemas.document_schema import DocumentInDB
from app.services.chunk_service import chunk_document
from app.services.ocr_service import process_document_ocr

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/{document_id}/ocr", response_model=DocumentInDB)
def run_document_ocr(
    document_id: int,
    db: Session = Depends(get_db),
):
    doc = (
        db.query(Document)
        .filter(Document.id == document_id, Document.is_deleted.is_(False))
        .first()
    )

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    updated = process_document_ocr(db, doc)
    return updated


@router.post("/{document_id}/chunk", response_model=List[ChunkInDB])
def run_document_chunk(
    document_id: int,
    db: Session = Depends(get_db),
    chunk_size: int = Query(1000, ge=200, le=4000),
    chunk_overlap: int = Query(200, ge=0, le=1000),
):
    doc = (
        db.query(Document)
        .filter(Document.id == document_id, Document.is_deleted.is_(False))
        .first()
    )

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Ensure document has OCR text
    if not doc.text_content:
        raise HTTPException(
            status_code=400,
            detail="Document has no text_content. Please run OCR first.",
        )

    return chunk_document(
        db=db,
        document_id=document_id,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
