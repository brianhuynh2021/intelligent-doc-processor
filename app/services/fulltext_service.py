"""Postgres full-text keyword search over documents.

Complements the semantic (vector) search in retrieval_service. Uses
plainto_tsquery so arbitrary user input is treated as plain terms (no
injection risk — query is a bound parameter), ranked with ts_rank and backed
by the idx_doc_fts GIN index.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

_TSVECTOR = (
    "to_tsvector('english', " "coalesce(name, '') || ' ' || coalesce(text_content, ''))"
)

_SEARCH_SQL = text(
    f"""
    SELECT id, name, status, owner_id,
           ts_rank({_TSVECTOR}, plainto_tsquery('english', :q)) AS rank
    FROM documents
    WHERE is_deleted = false
      AND (:owner_id IS NULL OR owner_id = :owner_id)
      AND {_TSVECTOR} @@ plainto_tsquery('english', :q)
    ORDER BY rank DESC
    LIMIT :limit
    """
)


@dataclass
class KeywordHit:
    id: int
    name: str
    status: str
    owner_id: int
    rank: float


def keyword_search(
    db: Session,
    query: str,
    *,
    owner_id: Optional[int] = None,
    limit: int = 10,
) -> list[KeywordHit]:
    rows = db.execute(
        _SEARCH_SQL,
        {"q": query, "owner_id": owner_id, "limit": limit},
    ).fetchall()
    return [
        KeywordHit(
            id=r.id,
            name=r.name,
            status=r.status,
            owner_id=r.owner_id,
            rank=float(r.rank or 0.0),
        )
        for r in rows
    ]
