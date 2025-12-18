from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.core.errors import NotFoundError
from app.models.document_model import Document
from app.schemas.chunk_schema import ChunkInDB
from app.schemas.document_schema import (
    DocumentInDB,
    DocumentListResponse,
    IngestionResponse,
    IngestionStep,
)
from app.services.chunk_service import chunk_document
from app.services.ingestion_pipeline import DocumentIngestionPipeline
from app.services.ocr_service import process_document_ocr

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_model=DocumentListResponse)
def list_documents(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user=Depends(get_current_user),
):
    query = db.query(Document).filter(Document.is_deleted.is_(False))
    if not getattr(current_user, "is_admin", False):
        query = query.filter(Document.owner_id == current_user.id)
    total = query.count()
    docs = query.order_by(Document.created_at.desc()).offset(skip).limit(limit).all()
    return DocumentListResponse(
        items=[DocumentInDB.model_validate(d) for d in docs],
        total=total,
    )


@router.get("/{document_id}", response_model=DocumentInDB)
def get_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    doc = (
        db.query(Document)
        .filter(Document.id == document_id, Document.is_deleted.is_(False))
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentInDB.model_validate(doc)


@router.delete("/{document_id}", response_model=DocumentInDB)
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    doc = (
        db.query(Document)
        .filter(Document.id == document_id, Document.is_deleted.is_(False))
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    doc.is_deleted = True
    doc.status = "deleted"
    doc.deleted_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(doc)
    return DocumentInDB.model_validate(doc)


@router.post("/{document_id}/ocr", response_model=DocumentInDB)
def run_document_ocr(
    document_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
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
    current_user=Depends(get_current_user),
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


@router.post("/{document_id}/ingest", response_model=IngestionResponse)
def run_document_ingestion(
    document_id: int,
    db: Session = Depends(get_db),
    chunk_size: int = Query(1000, ge=200, le=4000),
    chunk_overlap: int = Query(200, ge=0, le=1000),
    current_user=Depends(get_current_user),
):
    """
    End-to-end ingestion: OCR -> chunk -> embed -> store.
    """
    pipeline = DocumentIngestionPipeline(db=db)

    try:
        result = pipeline.run(
            document_id=document_id,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
    except ValueError as exc:
        raise NotFoundError(str(exc))

    return IngestionResponse(
        document=DocumentInDB.model_validate(result.document),
        total_duration_ms=result.total_duration_ms,
        chunks_indexed=result.chunks_indexed,
        steps=[IngestionStep(**s.__dict__) for s in result.steps],
    )
