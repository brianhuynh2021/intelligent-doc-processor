"""Hybrid search: fuse semantic (vector) and keyword (full-text) results with
Reciprocal Rank Fusion (RRF).

Semantic search is chunk-level and keyword search is document-level, so fusion
happens at the **document** level: semantic chunk hits are collapsed to their
best-ranked document, then RRF combines the two document rankings. RRF needs
only rank positions (not comparable scores), which is exactly why it suits
fusing a cosine score and a ts_rank.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.services.fulltext_service import keyword_search
from app.services.retrieval_service import semantic_search

RRF_K = 60  # standard constant; dampens the weight of top ranks


@dataclass
class HybridHit:
    document_id: int
    name: Optional[str]
    rrf_score: float
    semantic_rank: Optional[int]  # 1-based position, None if absent
    keyword_rank: Optional[int]
    snippet: Optional[str]


def reciprocal_rank_fusion(
    rankings: list[list[int]], k: int = RRF_K
) -> dict[int, float]:
    """Each ranking is an ordered list of document ids (best first). Returns
    {doc_id: fused_score}."""
    scores: dict[int, float] = {}
    for ranking in rankings:
        for position, doc_id in enumerate(ranking):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + position + 1)
    return scores


def hybrid_search(
    db: Session,
    query: str,
    *,
    top_k: int = 5,
    owner_id: Optional[int] = None,
    qdrant_filter: Any = None,
    candidate_factor: int = 3,
) -> list[HybridHit]:
    fetch = max(top_k * candidate_factor, top_k)

    # 1) Semantic (chunk-level) → collapse to best document order
    sem = semantic_search(
        query, top_k=fetch, use_mmr=False, qdrant_filter=qdrant_filter
    )
    sem_docs: list[int] = []
    snippet: dict[int, str] = {}
    name: dict[int, Optional[str]] = {}
    seen: set[int] = set()
    for hit in sem.hits:
        did = (hit.payload or {}).get("document_id")
        if did is None:
            continue
        did = int(did)
        if did not in seen:
            seen.add(did)
            sem_docs.append(did)
            snippet[did] = hit.text
            name[did] = (hit.payload or {}).get("document_name")

    # 2) Keyword (document-level)
    kw = keyword_search(db, query, owner_id=owner_id, limit=fetch)
    kw_docs = [h.id for h in kw]
    for h in kw:
        name.setdefault(h.id, h.name)

    # 3) Fuse
    fused = reciprocal_rank_fusion([sem_docs, kw_docs])
    sem_pos = {d: i + 1 for i, d in enumerate(sem_docs)}
    kw_pos = {d: i + 1 for i, d in enumerate(kw_docs)}

    ranked = sorted(fused.items(), key=lambda kv: kv[1], reverse=True)[:top_k]
    return [
        HybridHit(
            document_id=did,
            name=name.get(did),
            rrf_score=round(score, 6),
            semantic_rank=sem_pos.get(did),
            keyword_rank=kw_pos.get(did),
            snippet=snippet.get(did),
        )
        for did, score in ranked
    ]
