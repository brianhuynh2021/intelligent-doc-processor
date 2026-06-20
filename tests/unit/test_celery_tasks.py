"""Unit test for the Celery document-processing task.

Runs the task synchronously (eager) with the pipeline mocked, so no broker or
real services are needed.
"""
from unittest.mock import MagicMock, patch

from app.core.celery_app import celery_app
from app.tasks import document_tasks


def test_celery_app_configured():
    assert celery_app.main == "doc_processor"
    assert "app.tasks.document_tasks" in celery_app.conf.include
    # the task is registered
    assert "process_document" in celery_app.tasks


def test_process_document_task_runs_pipeline(monkeypatch):
    fake_result = MagicMock(chunks_indexed=3, total_duration_ms=1234)
    fake_pipeline = MagicMock()
    fake_pipeline.run.return_value = fake_result

    monkeypatch.setattr(document_tasks, "SessionLocal", MagicMock())
    monkeypatch.setattr(
        document_tasks,
        "DocumentIngestionPipeline",
        MagicMock(return_value=fake_pipeline),
    )

    # call the task body directly (eager)
    out = document_tasks.process_document_task.run(
        document_id=14, chunk_size=500, chunk_overlap=100
    )

    assert out == {
        "document_id": 14,
        "status": "completed",
        "chunks_indexed": 3,
        "duration_ms": 1234,
    }
    fake_pipeline.run.assert_called_once_with(
        document_id=14, chunk_size=500, chunk_overlap=100
    )


def test_process_document_task_propagates_error(monkeypatch):
    fake_pipeline = MagicMock()
    fake_pipeline.run.side_effect = RuntimeError("boom")
    monkeypatch.setattr(document_tasks, "SessionLocal", MagicMock())
    monkeypatch.setattr(
        document_tasks,
        "DocumentIngestionPipeline",
        MagicMock(return_value=fake_pipeline),
    )

    with patch.object(document_tasks.logger, "error"):
        try:
            document_tasks.process_document_task.run(document_id=99)
            assert False, "expected RuntimeError"
        except RuntimeError as e:
            assert "boom" in str(e)
