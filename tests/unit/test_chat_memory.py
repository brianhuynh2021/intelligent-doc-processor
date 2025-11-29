import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.chat_message_model import ChatMessage
from app.models.chat_session_model import ChatSession
from app.services import chat_service, rag_service
from app.services.retrieval_service import RetrievalResult


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine, tables=[ChatSession.__table__, ChatMessage.__table__])
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_chat_service_persists_and_fetches_history(db_session):
    session = chat_service.create_session(db_session, name="test")
    chat_service.add_message(db_session, session.id, "user", "hello")
    chat_service.add_message(db_session, session.id, "assistant", "hi there")

    history = chat_service.get_messages(db_session, session_id=session.id, limit=10)
    assert [m.role for m in history] == ["user", "assistant"]
    assert history[0].content == "hello"


def test_answer_question_trims_history(monkeypatch):
    # Mock retrieval
    monkeypatch.setattr(
        rag_service,
        "semantic_search",
        lambda **kwargs: RetrievalResult(hits=[], used_mmr=True, total_candidates=0),
    )

    captured = {}

    def fake_openai(model_name, messages, stream=False):
        captured["messages"] = messages
        return "answer"

    monkeypatch.setattr(rag_service, "_call_openai_chat", fake_openai)

    history = [
        ChatMessage(session_id=1, role="user", content="old q"),
        ChatMessage(session_id=1, role="assistant", content="old a"),
        ChatMessage(session_id=1, role="user", content="recent q"),
    ]

    answer, contexts, model_used = rag_service.answer_question(
        question="new question",
        model="gpt-4o",
        history=history,
        max_history_messages=2,
    )

    assert answer == "answer"
    assert model_used == "gpt-4o"
    # Should include only last 2 messages (assistant old a, user recent q)
    assert "old q" not in str(captured["messages"])
    assert "recent q" in str(captured["messages"])
