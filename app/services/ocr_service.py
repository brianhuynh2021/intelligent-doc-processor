from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List

from sqlalchemy.orm import Session

from app.core.errors import DependencyMissingError
from app.models.document_model import Document


@dataclass
class PageOcrResult:
    page_number: int
    text: str


def ocr_pdf_file(pdf_path: str) -> List[PageOcrResult]:
    """
    Extract text from PDF pages using PyPDF (no OCR for scanned images).
    """
    try:
        from pypdf import PdfReader  # type: ignore
    except ModuleNotFoundError as exc:
        raise DependencyMissingError(
            "pypdf is required to extract text from PDFs",
            details=[{"dependency": "pypdf"}],
        ) from exc

    reader = PdfReader(pdf_path)
    page_results: List[PageOcrResult] = []

    for idx, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        page_results.append(PageOcrResult(page_number=idx, text=text))

    return page_results


def process_document_ocr(db: Session, document: Document):
    started_at = datetime.now(timezone.utc)
    document.processing_started_at = started_at
    document.status = "processing"
    document.processing_step = "ocr"
    document.processing_progress = 0
    document.processing_completed_at = None
    document.processing_duration_ms = None
    document.last_error = None
    db.commit()

    try:
        # Run OCR
        pages = ocr_pdf_file(document.file_path)
        full_text = "\n\n".join(f"[Page {p.page_number}]\n{p.text}" for p in pages)

        # Save result
        document.text_content = full_text
        document.status = "processing"
        document.processing_step = "ocr"
        document.processing_progress = 35
        finished_at = datetime.now(timezone.utc)
        document.processing_duration_ms = int(
            (finished_at - started_at).total_seconds() * 1000
        )

    except Exception as e:
        document.status = "error"
        document.error_count = (document.error_count or 0) + 1
        document.last_error = str(e)
        document.processing_progress = document.processing_progress or 0
        document.processing_step = "error"
        document.processing_completed_at = datetime.now(timezone.utc)
        document.processing_duration_ms = int(
            (document.processing_completed_at - started_at).total_seconds() * 1000
        )

    db.commit()
    db.refresh(document)
    return document
