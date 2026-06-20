"""Celery application for background document processing.

Broker + result backend are Redis (separate DBs from the cache). Tasks live in
app.tasks.* and are auto-discovered via the ``include`` list.
"""
from __future__ import annotations

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "doc_processor",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.document_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,  # report STARTED state, not just PENDING->SUCCESS
    task_time_limit=600,  # hard kill after 10 min
    task_soft_time_limit=540,
    result_expires=3600,  # results TTL 1h
    worker_max_tasks_per_child=50,  # recycle workers to bound memory
)
