from app.services import retrieval_service
from app.services.retrieval_service import mmr_rerank


def make_point(pid, vector, score, payload=None):
    class _Point:
        def __init__(self, pid, vector, score, payload):
            self.id = pid
            self.vector = vector
            self.score = score
            self.payload = payload

    return _Point(pid, vector, score, payload or {"text": f"{pid}_text"})


def test_mmr_rerank_prefers_diversity():
    query_vec = [1.0, 0.0]
    points = [
        make_point("a", [1.0, 0.0], 0.9),
        make_point("b", [0.95, 0.05], 0.88),
        make_point("c", [0.0, 1.0], 0.7),
    ]

    reranked = mmr_rerank(query_vec, points, top_k=2, lambda_mult=0.3)

    assert reranked[0].id == "a"
    assert len(reranked) == 2
    assert {r.id for r in reranked} == {"a", "c"}


def test_semantic_search_threshold_and_no_mmr(monkeypatch):
    monkeypatch.setattr(
        retrieval_service,
        "embed_with_cache",
        lambda texts: [[1.0, 0.0]],
    )

    p1 = make_point("keep", [1.0, 0.0], 0.9)
    p2 = make_point("drop", [1.0, 0.0], 0.6)

    monkeypatch.setattr(
        retrieval_service,
        "search_similar",
        lambda **kwargs: [p1, p2],
    )

    result = retrieval_service.semantic_search(
        query="hello",
        top_k=3,
        score_threshold=0.8,
        use_mmr=False,
    )

    assert len(result.hits) == 1
    assert result.hits[0].id == "keep"
    assert result.used_mmr is False
