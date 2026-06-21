"""Unit tests for hybrid search (RRF fusion)."""
from types import SimpleNamespace

from app.services import hybrid_service
from app.services.hybrid_service import hybrid_search, reciprocal_rank_fusion


def test_rrf_rewards_agreement():
    # doc 1 ranks high in both lists -> should top the fused order
    rankings = [[1, 2, 3], [1, 3, 4]]
    scores = reciprocal_rank_fusion(rankings, k=60)
    order = sorted(scores, key=lambda d: scores[d], reverse=True)
    assert order[0] == 1  # appears first in both
    assert scores[1] > scores[2] and scores[1] > scores[4]


def test_rrf_single_list_preserves_order():
    scores = reciprocal_rank_fusion([[5, 6, 7]])
    assert scores[5] > scores[6] > scores[7]


def _hit(document_id, text, name):
    return SimpleNamespace(
        payload={"document_id": document_id, "document_name": name}, text=text
    )


def test_hybrid_search_fuses_and_dedups(monkeypatch):
    # semantic returns chunks of docs [10, 11]; keyword returns docs [11, 12]
    sem_result = SimpleNamespace(
        hits=[
            _hit(10, "chunk a", "Doc10"),
            _hit(10, "chunk a2", "Doc10"),  # duplicate doc -> collapses
            _hit(11, "chunk b", "Doc11"),
        ]
    )
    monkeypatch.setattr(hybrid_service, "semantic_search", lambda *a, **k: sem_result)
    kw_hits = [
        SimpleNamespace(id=11, name="Doc11"),
        SimpleNamespace(id=12, name="Doc12"),
    ]
    monkeypatch.setattr(hybrid_service, "keyword_search", lambda *a, **k: kw_hits)

    out = hybrid_search(object(), "invoice", top_k=5)

    ids = [h.document_id for h in out]
    assert ids[0] == 11  # in both lists -> highest RRF
    assert set(ids) == {10, 11, 12}  # union, deduped
    by_id = {h.document_id: h for h in out}
    assert by_id[11].semantic_rank == 2 and by_id[11].keyword_rank == 1
    assert by_id[12].semantic_rank is None  # keyword-only
    assert by_id[10].snippet == "chunk a"  # best chunk snippet kept
