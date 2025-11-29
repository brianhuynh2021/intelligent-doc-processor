from fastapi import APIRouter, HTTPException, Depends
from qdrant_client.models import FieldCondition, Filter, MatchValue, Range

from app.core.auth import get_current_user
from app.schemas.search_schema import (
    SearchFilter,
    SearchRequest,
    SearchResponse,
    SearchResult,
)
from app.services.retrieval_service import semantic_search

router = APIRouter(prefix="/search", tags=["search"], dependencies=[Depends(get_current_user)])


def build_qdrant_filter(filter_obj: SearchFilter | None) -> Filter | None:
    if filter_obj is None:
        return None

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
def semantic_search_endpoint(body: SearchRequest):
    try:
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
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return SearchResponse(
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
