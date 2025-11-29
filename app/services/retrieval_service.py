from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

from qdrant_client.models import ScoredPoint

from app.services.embedding_service import embed_with_cache
from app.services.vector_store import search_similar


@dataclass
class RetrievalHit:
    id: str | int | None
    score: float
    text: Optional[str]
    payload: Dict[str, Any]


@dataclass
class RetrievalResult:
    hits: List[RetrievalHit]
    used_mmr: bool
    total_candidates: int


def cosine_similarity(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def mmr_rerank(
    query_vec: List[float],
    candidates: List[ScoredPoint],
    top_k: int,
    lambda_mult: float = 0.5,
) -> List[ScoredPoint]:
    """Simple MMR rerank using vectors returned from Qdrant."""
    if not candidates:
        return []

    selected: List[ScoredPoint] = []
    candidate_pool = list(candidates)

    # Precompute similarities of query to all candidates
    query_sims = [cosine_similarity(query_vec, p.vector or []) for p in candidate_pool]

    while candidate_pool and len(selected) < top_k:
        mmr_scores = []
        for idx, cand in enumerate(candidate_pool):
            sim_to_query = query_sims[idx]
            sim_to_selected = 0.0
            if selected:
                sim_to_selected = max(
                    cosine_similarity(cand.vector or [], s.vector or [])
                    for s in selected
                )
            score = lambda_mult * sim_to_query - (1 - lambda_mult) * sim_to_selected
            mmr_scores.append((score, idx, cand))

        # Pick best candidate
        mmr_scores.sort(key=lambda x: x[0], reverse=True)
        _, best_idx, best_point = mmr_scores[0]
        selected.append(best_point)
        # Remove from pools
        candidate_pool.pop(best_idx)
        query_sims.pop(best_idx)

    return selected


def semantic_search(
    query: str,
    *,
    top_k: int = 5,
    fetch_k: Optional[int] = None,
    filters: Optional[Dict[str, Any]] = None,
    score_threshold: Optional[float] = None,
    use_mmr: bool = True,
    mmr_lambda: float = 0.5,
    qdrant_filter=None,
) -> RetrievalResult:
    """
    Run semantic search with optional metadata filters, score threshold, and MMR reranking.
    """
    query_vec = embed_with_cache([query])[0]

    candidate_limit = fetch_k or max(top_k * 3, top_k)
    points: List[ScoredPoint] = search_similar(
        query_vector=query_vec,
        limit=candidate_limit,
        filter_metadata=filters,
        score_threshold=score_threshold,
        with_vectors=use_mmr,
        custom_filter=qdrant_filter,
    )

    # Local threshold filtering (if Qdrant didn't filter by score)
    if score_threshold is not None:
        points = [p for p in points if (p.score or 0) >= score_threshold]

    if use_mmr:
        reranked = mmr_rerank(
            query_vec=query_vec,
            candidates=points,
            top_k=top_k,
            lambda_mult=mmr_lambda,
        )
    else:
        reranked = points[:top_k]

    hits = [
        RetrievalHit(
            id=p.id,
            score=p.score or 0.0,
            text=(p.payload or {}).get("text"),
            payload=p.payload or {},
        )
        for p in reranked
    ]

    return RetrievalResult(
        hits=hits,
        used_mmr=use_mmr,
        total_candidates=len(points),
    )
