"""Background tasks for document processing.

The ingestion pipeline already records status/progress on the Document row, so
the API can report progress by reading the document regardless of the Celery
result backend. The Celery result carries a compact summary.
"""
from __future__ import annotations

from typing import Any

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.core.logging import get_logger
from app.services.ingestion_pipeline import DocumentIngestionPipeline

logger = get_logger(__name__)


@celery_app.task(bind=True, name="process_document", max_retries=2)
def process_document_task(
    self,
    document_id: int,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> dict[str, Any]:
    """Run the full ingestion pipeline (OCR → chunk → embed → store) for a
    document in the background. Uses its own DB session (worker process)."""
    db = SessionLocal()
    try:
        logger.info("task_process_document_start", document_id=document_id)
        pipeline = DocumentIngestionPipeline(db=db)
        result = pipeline.run(
            document_id=document_id,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        logger.info(
            "task_process_document_done",
            document_id=document_id,
            chunks_indexed=result.chunks_indexed,
        )
        return {
            "document_id": document_id,
            "status": "completed",
            "chunks_indexed": result.chunks_indexed,
            "duration_ms": result.total_duration_ms,
        }
    except Exception as exc:  # pipeline already marks the doc row as error
        logger.error(
            "task_process_document_failed",
            document_id=document_id,
            error=str(exc),
        )
        raise
    finally:
        db.close()
