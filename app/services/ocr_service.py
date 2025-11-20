from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List

import pytesseract
from pdf2image import convert_from_path
from PIL import Image
from sqlalchemy.orm import Session

from app.core.config import POPPLER_PATH, TESSERACT_CMD
from app.models.document_model import Document

pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD


@dataclass
class PageOcrResult:
    page_number: int
    text: str


def pdf_to_images(pdf_path: str) -> List[Image.Image]:
    """
    Convert một PDF thành list ảnh (mỗi trang là một Image).
    """
    images = convert_from_path(
        pdf_path,
        dpi=300,
        poppler_path=POPPLER_PATH,
    )
    return images


def ocr_image(image: Image.Image, page_number: int) -> PageOcrResult:
    """
    Chạy OCR cho một trang ảnh.
    """
    text = pytesseract.image_to_string(image, lang="eng+vie")
    return PageOcrResult(page_number=page_number, text=text)


def ocr_pdf_file(pdf_path: str) -> List[PageOcrResult]:
    """
    Full pipeline: PDF path -> list PageOcrResult (multi-page).
    """
    images = pdf_to_images(pdf_path)
    results: List[PageOcrResult] = []

    for idx, img in enumerate(images, start=1):
        page_result = ocr_image(img, page_number=idx)
        results.append(page_result)

    return results


def process_document_ocr(db: Session, document: Document):
    document.processing_started_at = datetime.now(timezone.utc)
    document.status = "processing"
    db.commit()

    try:
        # Run OCR
        pages = ocr_pdf_file(document.file_path)
        full_text = "\n\n".join(f"[Page {p.page_number}]\n{p.text}" for p in pages)

        # Save result
        document.text_content = full_text
        document.status = "completed"
        document.processing_completed_at = datetime.utcnow()

    except Exception as e:
        document.status = "error"
        document.error_count += 1
        document.last_error = str(e)

    db.commit()
    db.refresh(document)
    return document
