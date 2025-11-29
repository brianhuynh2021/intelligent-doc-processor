import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.database import get_db
from app.models import Base
from app.services import rag_service
from app.services.retrieval_service import RetrievalHit
from app.core.auth import get_current_user


@pytest.fixture(scope="module")
def test_db():
    engine = create_engine(
        "sqlite:///file:chatmemdb?mode=memory&cache=shared",
        connect_args={"check_same_thread": False, "uri": True},
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    from app.models.chat_session_model import ChatSession
    from app.models.chat_message_model import ChatMessage

    Base.metadata.create_all(bind=engine, tables=[ChatSession.__table__, ChatMessage.__table__])

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: type("U", (), {"id": 1})()
    yield TestingSessionLocal
    app.dependency_overrides.clear()


@pytest.fixture()
def client(test_db):
    return TestClient(app)


def test_chat_creates_session_and_persists_messages(monkeypatch, client, test_db):
    # Mock RAG answer
    def fake_answer_question(**kwargs):
        hit = RetrievalHit(id="1", score=0.9, text="ctx", payload={})
        return "mock answer", [hit], "gpt-4o"

    monkeypatch.setattr(rag_service, "answer_question", fake_answer_question)
    monkeypatch.setattr("app.api.v1.routers.chat_router.answer_question", fake_answer_question)

    payload = {
        "question": "Hello?",
        "top_k": 2,
        "stream": False,
    }
    resp = client.post("/api/v1/chat/ask", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["answer"] == "mock answer"
    session_id = data["session_id"]

    # Ask again using same session
    payload["session_id"] = session_id
    resp2 = client.post("/api/v1/chat/ask", json=payload)
    assert resp2.status_code == 200

    # Check messages stored
    SessionLocal = test_db
    db = SessionLocal()
    try:
        from app.models.chat_message_model import ChatMessage

        msgs = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).all()
        assert len(msgs) == 4  # 2 user + 2 assistant
    finally:
        db.close()
