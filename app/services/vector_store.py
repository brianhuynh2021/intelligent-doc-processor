"""
Vector store integration using Qdrant.

This module is responsible for:
- Ensuring the collection exists with the correct vector size
- Upserting (inserting/updating) embeddings with metadata
- Searching similar vectors for retrieval
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional
from uuid import uuid4

from app.core.config import settings
from app.core.errors import DependencyMissingError, UpstreamServiceError
from app.core.retry import retry_transient

if TYPE_CHECKING:  # pragma: no cover
    from qdrant_client import QdrantClient
    from qdrant_client.models import Filter

COLLECTION_NAME = settings.QDRANT_COLLECTION
_client: "QdrantClient | None" = None


def _get_client() -> "QdrantClient":
    global _client
    if _client is None:
        try:
            from qdrant_client import QdrantClient  # type: ignore
        except ModuleNotFoundError as exc:
            raise DependencyMissingError(
                "qdrant-client is required for vector store operations",
                details=[{"dependency": "qdrant-client"}],
            ) from exc
        _client = QdrantClient(
            url=settings.QDRANT_URL,
            api_key=getattr(settings, "QDRANT_API_KEY", None) or None,
        )
    return _client


def _import_models():
    try:
        from qdrant_client.models import (  # type: ignore
            Distance,
            FieldCondition,
            Filter,
            FilterSelector,
            MatchValue,
            PointStruct,
            VectorParams,
        )
    except ModuleNotFoundError as exc:
        raise DependencyMissingError(
            "qdrant-client is required for vector store operations",
            details=[{"dependency": "qdrant-client"}],
        ) from exc
    return (
        Distance,
        Filter,
        FilterSelector,
        FieldCondition,
        MatchValue,
        PointStruct,
        VectorParams,
    )


def _collection_exists() -> bool:
    client = _get_client()

    @retry_transient
    def _exists() -> bool:
        return client.collection_exists(COLLECTION_NAME)

    try:
        return _exists()
    except Exception as exc:
        raise UpstreamServiceError(
            "Vector store unavailable",
            details=[{"provider": "qdrant", "collection": COLLECTION_NAME}],
        ) from exc


def ensure_collection(vector_size: int) -> None:
    """
    Create the collection if it does not exist yet.

    This should be called before the first upsert to guarantee
    that Qdrant is configured with the correct vector size.
    """
    Distance, _, _, _, _, _, VectorParams = _import_models()
    client = _get_client()

    @retry_transient
    def _recreate() -> None:
        client.recreate_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )

    try:
        if _collection_exists():
            return
        _recreate()
    except Exception as exc:
        raise UpstreamServiceError(
            "Vector store unavailable",
            details=[{"provider": "qdrant", "collection": COLLECTION_NAME}],
        ) from exc


def upsert_embeddings(
    ids: List[str],
    vectors: List[List[float]],
    metadatas: List[Dict[str, Any]],
) -> None:
    """
    Store or update embeddings in Qdrant.

    - ids: unique identifiers for each point (e.g., "fileid_page_chunk")
    - vectors: list of embedding vectors
    - metadatas: associated metadata payloads (file_id, page, text, etc.)
    """
    if not ids:
        return

    if not (len(ids) == len(vectors) == len(metadatas)):
        raise ValueError("ids, vectors and metadatas must have the same length")

    # Ensure collection exists with the correct vector dimension
    vector_size = len(vectors[0])
    ensure_collection(vector_size)

    *_, PointStruct, _ = _import_models()
    client = _get_client()

    points: List[Any] = []
    for i in range(len(ids)):
        # Copy metadata to avoid mutating the original
        payload = dict(metadatas[i])
        # Preserve the original logical ID inside the payload for traceability
        payload.setdefault("logical_id", ids[i])

        points.append(
            PointStruct(
                id=str(uuid4()),  # Qdrant point ID must be an unsigned int or UUID
                vector=vectors[i],
                payload=payload,
            )
        )

    @retry_transient
    def _upsert() -> None:
        client.upsert(collection_name=COLLECTION_NAME, points=points, wait=True)

    try:
        _upsert()
    except Exception as exc:
        raise UpstreamServiceError(
            "Vector store unavailable",
            details=[{"provider": "qdrant", "collection": COLLECTION_NAME}],
        ) from exc


def search_similar(
    query_vector: List[float],
    limit: int = 5,
    filter_metadata: Optional[Dict[str, Any]] = None,
    score_threshold: Optional[float] = None,
    with_vectors: bool = False,
    custom_filter: Optional["Filter"] = None,
):
    """
    Search for the most similar documents given a query vector.

    - query_vector: embedding of the query text
    - limit: maximum number of results to return
    - filter_metadata: optional filtering on payload, e.g. {"file_id": "..."}
    - score_threshold: filter out results below this score (cosine similarity)
    - with_vectors: include stored vectors in the response (needed for MMR)
    """
    if not query_vector:
        return []

    _, Filter, _, FieldCondition, MatchValue, *_ = _import_models()
    client = _get_client()

    qdrant_filter: Optional[Any] = custom_filter

    # Build Qdrant filter from simple "field == value" conditions
    if filter_metadata and qdrant_filter is None:
        conditions = []
        for field, value in filter_metadata.items():
            conditions.append(
                FieldCondition(
                    key=field,
                    match=MatchValue(value=value),
                )
            )
        if conditions:
            qdrant_filter = Filter(must=conditions)

    @retry_transient
    def _search():
        return client.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_vector,
            limit=limit,
            query_filter=qdrant_filter,
            score_threshold=score_threshold,
            with_vectors=with_vectors,
        )

    try:
        return _search()
    except Exception as exc:
        raise UpstreamServiceError(
            "Vector store unavailable",
            details=[{"provider": "qdrant", "collection": COLLECTION_NAME}],
        ) from exc


def delete_embeddings_by_logical_ids(logical_ids: List[str]) -> None:
    """
    Remove points from the collection by their logical IDs (stored in payload).
    """
    if not logical_ids:
        return

    if not _collection_exists():
        return

    _, Filter, FilterSelector, FieldCondition, MatchValue, *_ = _import_models()
    client = _get_client()

    conditions = [
        FieldCondition(key="logical_id", match=MatchValue(value=lid))
        for lid in logical_ids
    ]
    selector = FilterSelector(filter=Filter(should=conditions))

    @retry_transient
    def _delete() -> None:
        client.delete(
            collection_name=COLLECTION_NAME, points_selector=selector, wait=True
        )

    try:
        _delete()
    except Exception as exc:
        raise UpstreamServiceError(
            "Vector store unavailable",
            details=[{"provider": "qdrant", "collection": COLLECTION_NAME}],
        ) from exc


def delete_embeddings_by_document_id(document_id: int) -> None:
    """
    Remove points from the collection by document_id stored in payload.
    """
    if not _collection_exists():
        return

    _, Filter, FilterSelector, FieldCondition, MatchValue, *_ = _import_models()
    client = _get_client()

    selector = FilterSelector(
        filter=Filter(
            must=[
                FieldCondition(
                    key="document_id",
                    match=MatchValue(value=document_id),
                )
            ]
        )
    )

    @retry_transient
    def _delete() -> None:
        client.delete(
            collection_name=COLLECTION_NAME, points_selector=selector, wait=True
        )

    try:
        _delete()
    except Exception as exc:
        raise UpstreamServiceError(
            "Vector store unavailable",
            details=[{"provider": "qdrant", "collection": COLLECTION_NAME}],
        ) from exc
