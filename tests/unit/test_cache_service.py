"""Unit tests for the generic result cache (cache_service).

Uses fakeredis so no real Redis is needed.
"""
import fakeredis
import pytest

from app.services import cache_service


@pytest.fixture(autouse=True)
def fake_redis(monkeypatch):
    client = fakeredis.FakeStrictRedis(decode_responses=True)
    monkeypatch.setattr(cache_service, "_client", client)
    cache_service.reset_stats()
    yield client


def test_make_key_is_stable_and_order_independent():
    k1 = cache_service.make_key("search", {"a": 1, "b": 2}, 5)
    k2 = cache_service.make_key("search", {"b": 2, "a": 1}, 5)
    assert k1 == k2
    assert k1.startswith("cache:search:")


def test_set_then_get_roundtrip_counts_hit():
    key = cache_service.make_key("search", "query", 5)
    assert cache_service.get_json(key) is None  # miss
    cache_service.set_json(key, {"results": [1, 2, 3]}, ttl=60)
    got = cache_service.get_json(key)  # hit
    assert got == {"results": [1, 2, 3]}
    assert cache_service.stats.hits == 1
    assert cache_service.stats.misses == 1
    assert cache_service.stats.hit_rate() == 0.5


def test_invalidate_namespace_clears_tracked_keys():
    for i in range(3):
        key = cache_service.make_key("search", f"q{i}")
        cache_service.set_json(key, {"i": i}, ttl=60)
    removed = cache_service.invalidate_namespace("search")
    assert removed == 3
    # all gone now
    for i in range(3):
        key = cache_service.make_key("search", f"q{i}")
        assert cache_service.get_json(key) is None


def test_invalidate_only_targets_its_namespace():
    s_key = cache_service.make_key("search", "q")
    r_key = cache_service.make_key("rag", "q")
    cache_service.set_json(s_key, {"x": 1}, ttl=60)
    cache_service.set_json(r_key, {"x": 2}, ttl=60)
    cache_service.invalidate_namespace("search")
    assert cache_service.get_json(s_key) is None
    assert cache_service.get_json(r_key) == {"x": 2}


def test_disabled_cache_is_noop(monkeypatch):
    monkeypatch.setattr(cache_service, "_client", None)
    key = cache_service.make_key("search", "q")
    cache_service.set_json(key, {"x": 1}, ttl=60)
    assert cache_service.get_json(key) is None
    assert cache_service.invalidate_namespace("search") == 0
