# services/embedding_cache.py
import hashlib
import json
from typing import List, Optional

from app.core.config import settings

try:
    import redis  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    redis = None  # type: ignore

REDIS_URL = settings.REDIS_URL
EMBED_CACHE_TTL_SECONDS = 60 * 60 * 24  # 1 day

redis_client = redis.from_url(REDIS_URL, decode_responses=True) if redis else None


def _make_cache_key(model: str, text: str) -> str:
    h = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return f"embed:{model}:{h}"


def get_cached_embeddings(model: str, texts: List[str]) -> List[Optional[List[float]]]:
    if redis_client is None:
        return [None for _ in texts]

    keys = [_make_cache_key(model, t) for t in texts]
    try:
        raw_values = redis_client.mget(keys)
    except Exception:
        return [None for _ in texts]

    results: List[Optional[List[float]]] = []

    for raw in raw_values:
        if raw is None:
            results.append(None)
        else:
            results.append(json.loads(raw))
    return results


def set_cached_embeddings(
    model: str, texts: List[str], vectors: List[List[float]]
) -> None:
    if redis_client is None:
        return

    try:
        pipe = redis_client.pipeline()
    except Exception:
        return

    for text, vec in zip(texts, vectors):
        key = _make_cache_key(model, text)
        pipe.setex(key, EMBED_CACHE_TTL_SECONDS, json.dumps(vec))
    try:
        pipe.execute()
    except Exception:
        return
