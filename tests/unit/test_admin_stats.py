from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1.routers.admin_router import router as admin_router
from app.core.auth import get_current_user
from app.core.database import get_db
from app.core.exception_handlers import register_exception_handlers
from app.models import Base
from app.models.chat_message_model import ChatMessage
from app.models.chat_session_model import ChatSession
from app.models.document_model import Document


@pytest.fixture()
def app_and_db():
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(admin_router, prefix="/api/v1")

    engine = create_engine(
        "sqlite:///file:adminstatsdb?mode=memory&cache=shared",
        connect_args={"check_same_thread": False, "uri": True},
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    Base.metadata.create_all(
        bind=engine,
        tables=[Document.__table__, ChatSession.__table__, ChatMessage.__table__],
    )

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: type(
        "U",
        (),
        {"id": 1, "is_admin": True},
    )()

    return app, TestingSessionLocal


@pytest.fixture()
def client(app_and_db):
    app, _ = app_and_db
    return TestClient(app)


@pytest.fixture()
def db_session(app_and_db):
    _, SessionLocal = app_and_db
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_documents_stats_counts_and_buckets(client: TestClient, db_session):
    now = datetime.now(timezone.utc)
    docs = [
        Document(
            name="d1",
            original_filename="d1.pdf",
            file_path="/tmp/d1",
            file_size=10,
            content_type="application/pdf",
            status="pending",
            owner_id=1,
            is_deleted=False,
            created_at=now - timedelta(days=2),
            updated_at=now - timedelta(hours=1),
        ),
        Document(
            name="d2",
            original_filename="d2.png",
            file_path="/tmp/d2",
            file_size=20,
            content_type="image/png",
            status="processing",
            owner_id=2,
            is_deleted=False,
            created_at=now - timedelta(days=1),
            updated_at=now - timedelta(days=2),
        ),
        Document(
            name="d3",
            original_filename="d3.pdf",
            file_path="/tmp/d3",
            file_size=30,
            content_type="application/pdf",
            status="completed",
            owner_id=1,
            is_deleted=False,
            created_at=now - timedelta(hours=2),
            updated_at=now - timedelta(hours=2),
        ),
        Document(
            name="d4",
            original_filename="d4.pdf",
            file_path="/tmp/d4",
            file_size=40,
            content_type="application/pdf",
            status="error",
            owner_id=3,
            is_deleted=False,
            created_at=now - timedelta(days=10),
            updated_at=now - timedelta(days=10),
        ),
        Document(
            name="deleted",
            original_filename="deleted.pdf",
            file_path="/tmp/deleted",
            file_size=50,
            content_type="application/pdf",
            status="completed",
            owner_id=1,
            is_deleted=True,
            created_at=now - timedelta(hours=1),
            updated_at=now - timedelta(hours=1),
        ),
    ]
    db_session.add_all(docs)
    db_session.commit()

    resp = client.get("/api/v1/admin/stats/documents")
    assert resp.status_code == 200
    data = resp.json()

    assert data["total"] == 4
    assert data["by_status"] == {
        "pending": 1,
        "processing": 1,
        "completed": 1,
        "error": 1,
    }
    assert data["by_content_type"]["application/pdf"] == 3
    assert data["by_content_type"]["image/png"] == 1
    assert data["updated_last_24h"] == 2


def test_chat_stats_counts(client: TestClient, db_session):
    now = datetime.now(timezone.utc)

    s1 = ChatSession(
        session_key="s1",
        name="Session 1",
        created_by_user_id=1,
        created_at=now - timedelta(days=2),
    )
    s2 = ChatSession(
        session_key="s2",
        name="Session 2",
        created_by_user_id=2,
        created_at=now - timedelta(hours=2),
    )
    db_session.add_all([s1, s2])
    db_session.commit()
    db_session.refresh(s1)
    db_session.refresh(s2)

    msgs = [
        ChatMessage(
            session_id=s1.id,
            role="user",
            content="old",
            created_at=now - timedelta(days=3),
        ),
        ChatMessage(
            session_id=s1.id,
            role="assistant",
            content="old2",
            created_at=now - timedelta(days=2, minutes=1),
        ),
        ChatMessage(
            session_id=s2.id,
            role="user",
            content="hi",
            created_at=now - timedelta(hours=1),
        ),
        ChatMessage(
            session_id=s2.id,
            role="assistant",
            content="hello",
            created_at=now - timedelta(minutes=30),
        ),
    ]
    db_session.add_all(msgs)
    db_session.commit()

    resp = client.get("/api/v1/admin/stats/chat")
    assert resp.status_code == 200
    data = resp.json()

    assert data["total_sessions"] == 2
    assert data["total_messages"] == 4
    assert data["messages_last_24h"] == 2
    assert data["active_sessions_last_24h"] == 1


def test_stats_requires_admin(client: TestClient, app_and_db):
    app, _ = app_and_db
    app.dependency_overrides[get_current_user] = lambda: type(
        "U", (), {"id": 1, "is_admin": False}
    )()
    try:
        resp = client.get("/api/v1/admin/stats/documents")
        assert resp.status_code == 403
        payload = resp.json()
        assert payload["error"]["code"] == "forbidden"
    finally:
        app.dependency_overrides[get_current_user] = lambda: type(
            "U", (), {"id": 1, "is_admin": True}
        )()
