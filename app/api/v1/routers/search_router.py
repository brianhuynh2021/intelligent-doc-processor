from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.errors import DependencyMissingError
from app.core.rate_limit import limiter
from app.core.roles import UserRole, role_at_least
from app.schemas.search_schema import (
    SearchFilter,
    SearchRequest,
    SearchResponse,
    SearchResult,
)
from app.services import cache_service
from app.services.fulltext_service import keyword_search
from app.services.retrieval_service import semantic_search

router = APIRouter(
    prefix="/search", tags=["search"], dependencies=[Depends(get_current_user)]
)

if TYPE_CHECKING:  # pragma: no cover
    from qdrant_client.models import Filter


def build_qdrant_filter(filter_obj: SearchFilter | None) -> "Filter | None":
    if filter_obj is None:
        return None

    try:
        from qdrant_client.models import FieldCondition  # type: ignore
        from qdrant_client.models import Filter, MatchValue, Range
    except ModuleNotFoundError as exc:
        raise DependencyMissingError(
            "qdrant-client is required for search filters",
            details=[{"dependency": "qdrant-client"}],
        ) from exc

    conditions = []
    if filter_obj.document_id is not None:
        conditions.append(
            FieldCondition(
                key="document_id",
                match=MatchValue(value=filter_obj.document_id),
            )
        )
    if filter_obj.owner_id is not None:
        conditions.append(
            FieldCondition(
                key="owner_id",
                match=MatchValue(value=filter_obj.owner_id),
            )
        )
    if filter_obj.content_type:
        conditions.append(
            FieldCondition(
                key="content_type",
                match=MatchValue(value=filter_obj.content_type),
            )
        )

    range_kwargs = {}
    if filter_obj.created_from:
        range_kwargs["gte"] = int(filter_obj.created_from.timestamp())
    if filter_obj.created_to:
        range_kwargs["lte"] = int(filter_obj.created_to.timestamp())
    if range_kwargs:
        conditions.append(
            FieldCondition(
                key="document_created_at_ts",
                range=Range(**range_kwargs),
            )
        )

    if not conditions:
        return None

    return Filter(must=conditions)


@router.post("", response_model=SearchResponse)
@limiter.limit(settings.RATE_LIMIT_SEARCH)
def semantic_search_endpoint(request: Request, body: SearchRequest):
    cache_key = cache_service.make_key(
        "search",
        body.query,
        body.top_k,
        body.fetch_k,
        body.score_threshold,
        body.use_mmr,
        body.mmr_lambda,
        body.filters.model_dump(exclude_none=True) if body.filters else None,
    )
    cached = cache_service.get_json(cache_key)
    if cached is not None:
        return SearchResponse(**cached)

    qdrant_filter = build_qdrant_filter(body.filters)
    result = semantic_search(
        query=body.query,
        top_k=body.top_k,
        fetch_k=body.fetch_k,
        score_threshold=body.score_threshold,
        use_mmr=body.use_mmr,
        mmr_lambda=body.mmr_lambda,
        qdrant_filter=qdrant_filter,
    )

    response = SearchResponse(
        results=[
            SearchResult(
                id=hit.id,
                score=hit.score,
                text=hit.text,
                payload=hit.payload,
            )
            for hit in result.hits
        ],
        used_mmr=result.used_mmr,
        total_candidates=result.total_candidates,
    )
    cache_service.set_json(
        cache_key, response.model_dump(), ttl=settings.CACHE_TTL_SEARCH
    )
    return response


@router.get("/keyword")
@limiter.limit(settings.RATE_LIMIT_SEARCH)
def keyword_search_endpoint(
    request: Request,
    q: str = Query(..., min_length=1, max_length=1000, description="Search terms"),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Postgres full-text keyword search (complements semantic search).

    Non-admins are scoped to their own documents.
    """
    user_role = getattr(current_user, "role", None) or (
        "admin" if getattr(current_user, "is_admin", False) else "user"
    )
    owner_id = None if role_at_least(user_role, UserRole.ADMIN) else current_user.id
    hits = keyword_search(db, q, owner_id=owner_id, limit=limit)
    return {
        "query": q,
        "results": [
            {
                "id": h.id,
                "name": h.name,
                "status": h.status,
                "owner_id": h.owner_id,
                "rank": h.rank,
            }
            for h in hits
        ],
    }
