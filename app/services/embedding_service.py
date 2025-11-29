# services/embedding_service.py (bổ sung)
from typing import List
import os

from app.core.config import settings
from openai import OpenAI
from .embedding_cache import get_cached_embeddings, set_cached_embeddings

OPENAI_EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY") or settings.OPENAI_API_KEY
        _client = OpenAI(api_key=api_key)
    return _client


def embed_with_cache(texts: List[str]) -> List[List[float]]:
    """Dùng Redis cache + OpenAI embedding"""
    # 1. Lấy từ cache
    cached = get_cached_embeddings(OPENAI_EMBEDDING_MODEL, texts)

    # 2. Tìm những text chưa có embedding
    missing_indices = [i for i, v in enumerate(cached) if v is None]
    missing_texts = [texts[i] for i in missing_indices]

    # 3. Gọi OpenAI cho những cái thiếu
    if missing_texts:
        response = _get_client().embeddings.create(
            model=OPENAI_EMBEDDING_MODEL,
            input=missing_texts,
        )
        new_vectors = [item.embedding for item in response.data]

        # 4. Lưu cache
        set_cached_embeddings(OPENAI_EMBEDDING_MODEL, missing_texts, new_vectors)

        # 5. Gộp lại full list
        j = 0
        for i in missing_indices:
            cached[i] = new_vectors[j]
            j += 1

    # Lúc này cached đã đầy đủ
    return cached  # type: ignore
