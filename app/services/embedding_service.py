from __future__ import annotations

import os
from typing import TYPE_CHECKING, List

from app.core.config import settings
from app.core.errors import DependencyMissingError, UpstreamServiceError
from app.core.retry import retry_transient

from .embedding_cache import get_cached_embeddings, set_cached_embeddings

OPENAI_EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

if TYPE_CHECKING:  # pragma: no cover
    from openai import OpenAI

_client: "OpenAI | None" = None


def _get_client() -> "OpenAI":
    global _client
    if _client is None:
        try:
            from openai import OpenAI  # type: ignore
        except ModuleNotFoundError as exc:
            raise DependencyMissingError(
                "openai is required for embeddings",
                details=[{"dependency": "openai"}],
            ) from exc

        api_key = os.getenv("OPENAI_API_KEY") or settings.OPENAI_API_KEY
        _client = OpenAI(api_key=api_key)
    return _client


@retry_transient
def _create_embeddings(model: str, inputs: list[str]):
    return _get_client().embeddings.create(model=model, input=inputs)


def embed_with_cache(texts: List[str]) -> List[List[float]]:
    """Dùng Redis cache + OpenAI embedding"""
    # 1. Lấy từ cache
    cached = get_cached_embeddings(OPENAI_EMBEDDING_MODEL, texts)

    # 2. Tìm những text chưa có embedding
    missing_indices = [i for i, v in enumerate(cached) if v is None]
    missing_texts = [texts[i] for i in missing_indices]

    # 3. Gọi OpenAI cho những cái thiếu
    if missing_texts:
        try:
            response = _create_embeddings(OPENAI_EMBEDDING_MODEL, missing_texts)
        except Exception as exc:
            raise UpstreamServiceError(
                "Embedding provider failed",
                details=[{"provider": "openai", "model": OPENAI_EMBEDDING_MODEL}],
            ) from exc

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
