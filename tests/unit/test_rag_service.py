import pytest

from app.services import rag_service
from app.services.retrieval_service import RetrievalHit, RetrievalResult


def make_hits():
    return [
        RetrievalHit(id="1", score=0.9, text="A", payload={"chunk_index": 0}),
        RetrievalHit(id="2", score=0.8, text="B" * 5000, payload={"chunk_index": 1}),
    ]


def test_answer_question_uses_openai(monkeypatch):
    monkeypatch.setattr(
        rag_service,
        "semantic_search",
        lambda **kwargs: RetrievalResult(hits=make_hits(), used_mmr=True, total_candidates=2),
    )
    called = {}

    def fake_openai(model_name, messages, stream=False):
        called["model"] = model_name
        called["messages"] = messages
        return "openai answer"

    monkeypatch.setattr(rag_service, "_call_openai_chat", fake_openai)

    answer, contexts, model_used = rag_service.answer_question(
        question="hi", model="gpt-4o", max_context_chars=3, top_k=2
    )

    assert answer == "openai answer"
    assert model_used == "gpt-4o"
    # max_context_chars trims to first hit only ("A")
    assert len(contexts) == 1
    assert contexts[0].text == "A"
    assert called["messages"][0]["role"] == "system"
    assert called["messages"][1]["role"] in {"user", "human"}


def test_answer_question_uses_claude(monkeypatch):
    monkeypatch.setattr(
        rag_service,
        "semantic_search",
        lambda **kwargs: RetrievalResult(hits=make_hits(), used_mmr=True, total_candidates=2),
    )

    def fake_claude(model_name, messages):
        return f"claude answer via {model_name}"

    monkeypatch.setattr(rag_service, "_call_claude_chat", fake_claude)

    answer, contexts, model_used = rag_service.answer_question(
        question="hi", model="claude-3-sonnet-20240229", top_k=2
    )

    assert answer == "claude answer via claude-3-sonnet-20240229"
    assert model_used.startswith("claude-3")
    assert len(contexts) == 2
