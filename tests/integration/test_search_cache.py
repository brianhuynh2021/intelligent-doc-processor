"""E2E test: search endpoint caches results — second identical query is served
from cache without re-invoking the (expensive) semantic search."""
import fakeredis
import pytest
from fastapi.testclient import TestClient

from app.api.v1.routers import search_router
from app.core.auth import get_current_user
from app.main import app
from app.services import cache_service
from app.services.retrieval_service import RetrievalHit, RetrievalResult


@pytest.fixture()
def client(monkeypatch):
    # in-memory cache
    monkeypatch.setattr(
        cache_service, "_client", fakeredis.FakeStrictRedis(decode_responses=True)
    )
    cache_service.reset_stats()

    app.dependency_overrides[get_current_user] = lambda: type("U", (), {"id": 1})()
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_search_is_cached(client, monkeypatch):
    calls = {"n": 0}

    def fake_search(**kwargs):
        calls["n"] += 1
        return RetrievalResult(
            hits=[RetrievalHit(id="1", score=0.9, text="ctx", payload={})],
            used_mmr=True,
            total_candidates=1,
        )

    monkeypatch.setattr(search_router, "semantic_search", fake_search)

    body = {"query": "invoice total", "top_k": 5}
    r1 = client.post("/api/v1/search", json=body)
    r2 = client.post("/api/v1/search", json=body)

    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json() == r2.json()
    assert calls["n"] == 1  # second call served from cache
    assert cache_service.stats.hits == 1
