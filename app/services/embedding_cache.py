# services/embedding_cache.py
import hashlib
import json
import os
from typing import List, Optional
from app.core.config import settings
import redis

REDIS_URL = settings.REDIS_URL
EMBED_CACHE_TTL_SECONDS = 60 * 60 * 24  # 1 day

redis_client = redis.from_url(REDIS_URL, decode_responses=True)


def _make_cache_key(model: str, text: str) -> str:
    h = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return f"embed:{model}:{h}"


def get_cached_embeddings(model: str, texts: List[str]) -> List[Optional[List[float]]]:
    keys = [_make_cache_key(model, t) for t in texts]
    raw_values = redis_client.mget(keys)
    results: List[Optional[List[float]]] = []

    for raw in raw_values:
        if raw is None:
            results.append(None)
        else:
            results.append(json.loads(raw))
    return results


def set_cached_embeddings(model: str, texts: List[str], vectors: List[List[float]]) -> None:
    pipe = redis_client.pipeline()
    for text, vec in zip(texts, vectors):
        key = _make_cache_key(model, text)
        pipe.setex(key, EMBED_CACHE_TTL_SECONDS, json.dumps(vec))
    pipe.execute()
