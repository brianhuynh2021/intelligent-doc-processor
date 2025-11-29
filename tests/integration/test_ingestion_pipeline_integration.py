import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app.models.document_model import Document
from app.services.ingestion_pipeline import DocumentIngestionPipeline


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///file:ingestmemdb?mode=memory&cache=shared",
        connect_args={"check_same_thread": False, "uri": True},
    )
    Base.metadata.create_all(bind=engine, tables=[Document.__table__])
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_ingestion_pipeline_end_to_end(db_session):
    # Seed document
    doc = Document(
        name="demo.pdf",
        original_filename="demo.pdf",
        file_path="/tmp/demo.pdf",
        file_size=123,
        content_type="application/pdf",
        owner_id=1,
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)

    def fake_ocr(_doc):
        return "hello world"

    def fake_chunk(_doc, *_args, **_kwargs):
        return [
            {"id": "c1", "text": "hello", "chunk_index": 0, "document_owner_id": 1},
            {"id": "c2", "text": "world", "chunk_index": 1, "document_owner_id": 1},
        ]

    indexed = []

    def fake_index(chunks, _doc):
        indexed.extend([c["id"] for c in chunks])
        return indexed

    pipeline = DocumentIngestionPipeline(
        db=db_session,
        ocr_runner=fake_ocr,
        chunk_runner=fake_chunk,
        index_runner=fake_index,
    )

    result = pipeline.run(document_id=doc.id)

    db_session.refresh(doc)
    assert doc.status == "completed"
    assert doc.processing_progress == 100
    assert result.chunks_indexed == 2
