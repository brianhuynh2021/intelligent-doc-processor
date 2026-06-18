"""Generic Redis-backed result cache with stats and namespaced invalidation.

Falls back to no-op (cache miss) when Redis is unavailable, so the app keeps
working without a cache. The embedding cache lives separately in
``embedding_cache.py``; this module covers query/RAG result caching.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Optional

from app.core.config import settings
from app.core.logging import get_logger

try:
    import redis  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    redis = None  # type: ignore

logger = get_logger(__name__)

# TTLs (seconds) — tunable via env
SEARCH_CACHE_TTL = settings.CACHE_TTL_SEARCH
RAG_CACHE_TTL = settings.CACHE_TTL_RAG


class CacheStats:
    """In-process counters. Reset on restart; fine for a single worker and a
    good-enough signal for cache effectiveness in the demo."""

    def __init__(self) -> None:
        self.hits = 0
        self.misses = 0
        self.errors = 0

    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return round(self.hits / total, 4) if total else 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "hits": self.hits,
            "misses": self.misses,
            "errors": self.errors,
            "hit_rate": self.hit_rate(),
        }


stats = CacheStats()

_client = redis.from_url(settings.REDIS_URL, decode_responses=True) if redis else None


def _enabled() -> bool:
    return _client is not None


def make_key(namespace: str, *parts: Any) -> str:
    """Build a stable cache key. Long/variable parts are hashed so keys stay
    bounded and JSON-serializable values produce identical keys regardless of
    dict ordering."""
    payload = json.dumps(parts, sort_keys=True, default=str, ensure_ascii=False)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]
    return f"cache:{namespace}:{digest}"


def get_json(key: str) -> Optional[Any]:
    if not _enabled():
        return None
    try:
        raw = _client.get(key)  # type: ignore[union-attr]
    except Exception:  # pragma: no cover - redis runtime errors
        stats.errors += 1
        return None
    if raw is None:
        stats.misses += 1
        return None
    stats.hits += 1
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return None


def set_json(key: str, value: Any, ttl: int) -> None:
    if not _enabled():
        return
    try:
        _client.setex(key, ttl, json.dumps(value, default=str))  # type: ignore[union-attr]
        # Track the key under its namespace tag for targeted invalidation.
        namespace = key.split(":", 2)[1] if key.count(":") >= 2 else "default"
        _client.sadd(f"cacheidx:{namespace}", key)  # type: ignore[union-attr]
    except Exception:  # pragma: no cover
        stats.errors += 1


def invalidate_namespace(namespace: str) -> int:
    """Delete all cached entries tracked under a namespace. Returns count
    removed. Used e.g. when a document changes so stale search/RAG answers
    don't linger."""
    if not _enabled():
        return 0
    idx_key = f"cacheidx:{namespace}"
    try:
        keys = _client.smembers(idx_key)  # type: ignore[union-attr]
        if not keys:
            return 0
        pipe = _client.pipeline()  # type: ignore[union-attr]
        for k in keys:
            pipe.delete(k)
        pipe.delete(idx_key)
        pipe.execute()
        return len(keys)
    except Exception:  # pragma: no cover
        stats.errors += 1
        return 0


def reset_stats() -> None:
    stats.hits = 0
    stats.misses = 0
    stats.errors = 0
