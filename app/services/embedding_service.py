from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, List

from app.core.config import settings
from app.core.errors import DependencyMissingError, UpstreamServiceError
from app.core.retry import retry_transient

from .embedding_cache import get_cached_embeddings, set_cached_embeddings

OPENAI_EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

if TYPE_CHECKING:  # pragma: no cover
    from openai import OpenAI

_client: "OpenAI | None" = None
_gemini_client: Any | None = None


def _provider() -> str:
    return (settings.EMBEDDING_PROVIDER or "openai").lower()


def _active_model() -> str:
    """The embedding model in use — also the cache-key namespace, so switching
    providers never returns vectors from the wrong model/dimension."""
    if _provider() == "gemini":
        return settings.GEMINI_EMBEDDING_MODEL
    return OPENAI_EMBEDDING_MODEL


# ── OpenAI ──────────────────────────────────────────────────────────────────
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
def _embed_openai(model: str, inputs: list[str]) -> list[list[float]]:
    response = _get_client().embeddings.create(model=model, input=inputs)
    return [item.embedding for item in response.data]


# ── Gemini (google-genai) ───────────────────────────────────────────────────
def _get_gemini_client():
    global _gemini_client
    if _gemini_client is None:
        try:
            from google import genai  # type: ignore
        except ModuleNotFoundError as exc:
            raise DependencyMissingError(
                "google-genai is required for Gemini embeddings",
                details=[{"dependency": "google-genai"}],
            ) from exc
        api_key = settings.GEMINI_API_KEY or ""
        if not api_key:
            raise DependencyMissingError(
                "GEMINI_API_KEY is required for Gemini embeddings",
                details=[{"env": "GEMINI_API_KEY", "alt_env": "GOOGLE_API_KEY"}],
            )
        _gemini_client = genai.Client(api_key=api_key)
    return _gemini_client


@retry_transient
def _embed_gemini(model: str, inputs: list[str]) -> list[list[float]]:
    from google.genai import types  # type: ignore

    # gemini-embedding-001 defaults to 3072d; pin to EMBEDDING_DIM so vectors
    # match the Qdrant collection. COSINE distance is scale-invariant, so the
    # non-unit-norm of reduced dimensions is fine.
    resp = _get_gemini_client().models.embed_content(
        model=model,
        contents=inputs,
        config=types.EmbedContentConfig(output_dimensionality=settings.EMBEDDING_DIM),
    )
    return [list(e.values) for e in resp.embeddings]


def _embed_batch(model: str, inputs: list[str]) -> list[list[float]]:
    provider = _provider()
    try:
        if provider == "gemini":
            return _embed_gemini(model, inputs)
        return _embed_openai(model, inputs)
    except (DependencyMissingError, UpstreamServiceError):
        raise
    except Exception as exc:
        raise UpstreamServiceError(
            "Embedding provider failed",
            details=[{"provider": provider, "model": model}],
        ) from exc


def embed_with_cache(texts: List[str]) -> List[List[float]]:
    """Embed texts with a Redis cache, keyed by the active model so provider
    switches never mix dimensions."""
    model = _active_model()

    cached = get_cached_embeddings(model, texts)
    missing_indices = [i for i, v in enumerate(cached) if v is None]
    missing_texts = [texts[i] for i in missing_indices]

    if missing_texts:
        new_vectors = _embed_batch(model, missing_texts)
        set_cached_embeddings(model, missing_texts, new_vectors)
        for j, i in enumerate(missing_indices):
            cached[i] = new_vectors[j]

    return cached  # type: ignore
