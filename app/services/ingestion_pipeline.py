from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Callable, Iterable, List, Sequence

from sqlalchemy.orm import Session

from app.models.chunk_model import Chunk
from app.models.document_model import Document
from app.schemas.chunk_schema import ChunkInDB
from app.services.chunk_service import chunk_document
from app.services.indexing_pipeline import index_chunks
from app.services.ocr_service import ocr_pdf_file
from app.services.text_service import DEFAULT_CHUNK_OVERLAP, DEFAULT_CHUNK_SIZE
from app.services.vector_store import (
    delete_embeddings_by_document_id,
    delete_embeddings_by_logical_ids,
)

logger = logging.getLogger(__name__)


@dataclass
class PipelineStepReport:
    name: str
    duration_ms: int
    detail: str | None = None


@dataclass
class PipelineResult:
    document: Document
    steps: List[PipelineStepReport]
    chunks_indexed: int
    total_duration_ms: int


class DocumentIngestionPipeline:
    """
    Orchestrates the full ingestion flow:
    Upload (already done) -> OCR -> Chunk -> Embed -> Store.
    Tracks progress on the Document record and rolls back on failure.
    """

    STEP_PROGRESS = {
        "upload": 5,
        "ocr": 35,
        "chunk": 70,
        "embed_store": 100,
        "ingest": 100,
        "completed": 100,
        "error": 0,
    }

    def __init__(
        self,
        db: Session,
        *,
        ocr_runner: Callable[[Document], str] | None = None,
        chunk_runner: Callable[
            [Document, int, int], Sequence[ChunkInDB] | Iterable[Any]
        ]
        | None = None,
        index_runner: Callable[[Sequence[Any], Document], List[str]] | None = None,
        progress_callback: Callable[[Document], None] | None = None,
    ):
        self.db = db
        self.ocr_runner = ocr_runner or self._default_ocr_runner
        self.chunk_runner = chunk_runner or self._default_chunk_runner
        self.index_runner = index_runner or self._default_index_runner
        self.progress_callback = progress_callback

    def run(
        self,
        document_id: int,
        *,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    ) -> PipelineResult:
        document = self._get_document(document_id)
        start_clock = perf_counter()
        steps: List[PipelineStepReport] = []
        chunks: List[Any] = []
        logical_ids: List[str] = []

        self._mark_started(document)
        self._update_progress(document, "upload", "File registered")

        try:
            # OCR
            step_start = perf_counter()
            text = self.ocr_runner(document) or ""
            steps.append(
                PipelineStepReport(
                    name="ocr",
                    duration_ms=self._elapsed_ms(step_start),
                    detail=f"{len(text)} chars extracted",
                )
            )
            document.text_content = text
            self._update_progress(document, "ocr", "OCR completed")

            # Chunk
            step_start = perf_counter()
            chunks = list(self.chunk_runner(document, chunk_size, chunk_overlap))
            steps.append(
                PipelineStepReport(
                    name="chunk",
                    duration_ms=self._elapsed_ms(step_start),
                    detail=f"{len(chunks)} chunks created",
                )
            )
            self._update_progress(document, "chunk", "Chunking completed")

            # Embed + Store
            step_start = perf_counter()
            logical_ids = self.index_runner(chunks, document)
            steps.append(
                PipelineStepReport(
                    name="embed_store",
                    duration_ms=self._elapsed_ms(step_start),
                    detail=f"{len(logical_ids)} vectors stored",
                )
            )
            self._update_progress(document, "embed_store", "Embeddings stored")

            total_duration_ms = self._elapsed_ms(start_clock)
            self._mark_completed(document, total_duration_ms)

            return PipelineResult(
                document=document,
                steps=steps,
                chunks_indexed=len(logical_ids),
                total_duration_ms=total_duration_ms,
            )
        except Exception as exc:  # pragma: no cover - failure path validated separately
            self._handle_failure(document, exc, chunks, logical_ids, start_clock)
            raise

    # ---------- Default step implementations ----------
    def _default_ocr_runner(self, document: Document) -> str:
        pages = ocr_pdf_file(document.file_path)
        return "\n\n".join(f"[Page {p.page_number}]\n{p.text}" for p in pages)

    def _default_chunk_runner(
        self, document: Document, chunk_size: int, chunk_overlap: int
    ) -> Sequence[ChunkInDB]:
        return chunk_document(
            db=self.db,
            document_id=document.id,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            update_status=False,
        )

    def _default_index_runner(
        self, chunks: Sequence[Any], document: Document
    ) -> List[str]:
        payloads = [
            self._normalize_chunk_for_index(chunk, document, idx)
            for idx, chunk in enumerate(chunks)
        ]
        if payloads:
            delete_embeddings_by_document_id(document.id)
            index_chunks(payloads)
        return [p["id"] for p in payloads]

    # ---------- Helpers ----------
    def _get_document(self, document_id: int) -> Document:
        document = (
            self.db.query(Document)
            .filter(Document.id == document_id, Document.is_deleted.is_(False))
            .first()
        )
        if not document:
            raise ValueError(f"Document {document_id} not found or deleted")
        return document

    def _mark_started(self, document: Document) -> None:
        now = datetime.now(timezone.utc)
        document.status = "processing"
        document.processing_step = "starting"
        document.processing_progress = 0
        document.processing_started_at = now
        document.processing_completed_at = None
        document.processing_duration_ms = None
        document.last_error = None
        self.db.commit()
        self.db.refresh(document)

    def _mark_completed(self, document: Document, total_duration_ms: int) -> None:
        document.status = "completed"
        document.processing_step = "ingest"
        document.processing_progress = 100
        document.processing_completed_at = datetime.now(timezone.utc)
        document.processing_duration_ms = total_duration_ms
        self.db.commit()
        self.db.refresh(document)
        if self.progress_callback:
            self.progress_callback(document)

    def _handle_failure(
        self,
        document: Document,
        exc: Exception,
        chunks: Sequence[Any],
        logical_ids: Sequence[str],
        start_clock: float,
    ) -> None:
        logger.exception("Ingestion pipeline failed", exc_info=exc)

        self._rollback_chunks(document.id)
        self._rollback_embeddings(logical_ids)

        document.status = "error"
        document.processing_step = "error"
        document.processing_progress = document.processing_progress or 0
        document.processing_completed_at = datetime.now(timezone.utc)
        document.processing_duration_ms = self._elapsed_ms(start_clock)
        document.error_count = (document.error_count or 0) + 1
        document.last_error = str(exc)
        self.db.commit()
        self.db.refresh(document)
        if self.progress_callback:
            self.progress_callback(document)

    def _rollback_chunks(self, document_id: int) -> None:
        try:
            self.db.query(Chunk).filter(Chunk.document_id == document_id).delete()
            self.db.commit()
        except Exception as rollback_exc:  # pragma: no cover - defensive
            logger.warning(
                "Failed to rollback chunks for document %s: %s",
                document_id,
                rollback_exc,
            )

    def _rollback_embeddings(self, logical_ids: Sequence[str]) -> None:
        try:
            delete_embeddings_by_logical_ids(list(logical_ids))
        except Exception as rollback_exc:  # pragma: no cover - defensive
            logger.warning(
                "Failed to rollback embeddings for logical_ids=%s: %s",
                logical_ids,
                rollback_exc,
            )

    def _update_progress(
        self, document: Document, step: str, message: str | None
    ) -> None:
        progress_value = self.STEP_PROGRESS.get(step, document.processing_progress)
        document.processing_step = step
        document.processing_progress = progress_value
        document.status = "processing"
        self.db.commit()
        self.db.refresh(document)
        if self.progress_callback:
            self.progress_callback(document)
        if message:
            logger.info("[doc=%s] %s", document.id, message)

    def _normalize_chunk_for_index(
        self, chunk: Any, document: Document, fallback_index: int
    ) -> dict[str, Any]:
        # Accept dict, Pydantic model, or SQLAlchemy model
        data: dict[str, Any] = {}
        if isinstance(chunk, dict):
            data = dict(chunk)
        else:
            for attr in [
                "id",
                "content",
                "text",
                "chunk_index",
                "page_number",
                "page",
                "document_owner_id",
                "owner_id",
            ]:
                if hasattr(chunk, attr):
                    data[attr] = getattr(chunk, attr)

        text = data.get("content") or data.get("text")
        if not text:
            raise ValueError("Chunk missing text content for embedding")

        chunk_index = (
            data.get("chunk_index")
            if data.get("chunk_index") is not None
            else fallback_index
        )
        page = (
            data.get("page")
            if data.get("page") is not None
            else data.get("page_number")
        )
        owner_id = (
            data.get("document_owner_id") or data.get("owner_id") or document.owner_id
        )
        logical_id = str(data.get("id") or f"{document.id}_{chunk_index}")

        return {
            "id": logical_id,
            "text": text,
            "chunk_index": chunk_index,
            "page": page,
            "document_id": document.id,
            "document_owner_id": owner_id,
            "document_name": document.name,
            "document_original_filename": document.original_filename,
            "content_type": document.content_type,
            "document_created_at": document.created_at.isoformat()
            if document.created_at
            else None,
            "document_created_at_ts": int(document.created_at.timestamp())
            if document.created_at
            else None,
        }

    @staticmethod
    def _elapsed_ms(start_clock: float) -> int:
        return int((perf_counter() - start_clock) * 1000)
