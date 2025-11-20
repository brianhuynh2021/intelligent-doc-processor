from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.document_model import Document
from app.schemas.document_schema import DocumentInDB
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
