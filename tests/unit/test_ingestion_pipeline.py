import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.document_model import Document
from app.services.ingestion_pipeline import DocumentIngestionPipeline


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine, tables=[Document.__table__])
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def document(db_session):
    doc = Document(
        name="sample.pdf",
        original_filename="sample.pdf",
        file_path="/tmp/sample.pdf",
        file_size=123,
        content_type="application/pdf",
        owner_id=1,
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)
    return doc


def test_ingestion_pipeline_happy_path(db_session, document):
    def fake_ocr(_: Document) -> str:
        return "hello world"

    def fake_chunk(_: Document, __: int, ___: int):
        return [
            {"id": "c1", "text": "hello", "chunk_index": 0, "document_owner_id": 1},
            {"id": "c2", "text": "world", "chunk_index": 1, "document_owner_id": 1},
        ]

    def fake_index(chunks, _doc):
        return [c["id"] for c in chunks]

    pipeline = DocumentIngestionPipeline(
        db=db_session,
        ocr_runner=fake_ocr,
        chunk_runner=fake_chunk,
        index_runner=fake_index,
    )

    result = pipeline.run(document.id, chunk_size=500, chunk_overlap=0)
    db_session.refresh(document)

    assert document.status == "completed"
    assert document.processing_step == "completed"
    assert document.processing_progress == 100
    assert document.text_content == "hello world"
    assert document.processing_started_at is not None
    assert document.processing_completed_at is not None
    assert document.processing_duration_ms == result.total_duration_ms
    assert result.chunks_indexed == 2
    assert [s.name for s in result.steps] == ["ocr", "chunk", "embed_store"]


def test_ingestion_pipeline_marks_error_and_rolls_back(db_session, document):
    def fake_ocr(_: Document) -> str:
        return "hello world"

    def failing_chunk(*_args, **_kwargs):
        raise RuntimeError("chunking failed")

    pipeline = DocumentIngestionPipeline(
        db=db_session,
        ocr_runner=fake_ocr,
        chunk_runner=failing_chunk,
        index_runner=lambda chunks, doc: [],
    )

    with pytest.raises(RuntimeError):
        pipeline.run(document.id)

    db_session.refresh(document)

    assert document.status == "error"
    assert document.processing_step == "error"
    assert document.processing_progress == 35  # stuck after OCR step
    assert document.error_count == 1
    assert document.last_error.startswith("chunking failed")
    assert document.processing_duration_ms is not None
