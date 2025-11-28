"""
Vector store integration using Qdrant.

This module is responsible for:
- Ensuring the collection exists with the correct vector size
- Upserting (inserting/updating) embeddings with metadata
- Searching similar vectors for retrieval
"""

from typing import Any, Dict, List, Optional
from uuid import uuid4

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    Filter,
    FieldCondition,
    MatchValue,
    PointStruct,
    VectorParams,
)

from app.core.config import settings

# Initialize Qdrant client from global settings
qdrant_client = QdrantClient(
    url=settings.QDRANT_URL,
    api_key=getattr(settings, "QDRANT_API_KEY", None) or None,
)

COLLECTION_NAME = settings.QDRANT_COLLECTION


def ensure_collection(vector_size: int) -> None:
    """
    Create the collection if it does not exist yet.

    This should be called before the first upsert to guarantee
    that Qdrant is configured with the correct vector size.
    """
    if qdrant_client.collection_exists(COLLECTION_NAME):
        return

    qdrant_client.recreate_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(
            size=vector_size,
            distance=Distance.COSINE,
        ),
    )


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

    points: List[PointStruct] = []
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

    qdrant_client.upsert(
        collection_name=COLLECTION_NAME,
        points=points,
        wait=True,
    )


def search_similar(
    query_vector: List[float],
    limit: int = 5,
    filter_metadata: Optional[Dict[str, Any]] = None,
):
    """
    Search for the most similar documents given a query vector.

    - query_vector: embedding of the query text
    - limit: maximum number of results to return
    - filter_metadata: optional filtering on payload, e.g. {"file_id": "..."}
    """
    if not query_vector:
        return []

    qdrant_filter: Optional[Filter] = None

    # Build Qdrant filter from simple "field == value" conditions
    if filter_metadata:
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

    search_result = qdrant_client.search(
        collection_name=COLLECTION_NAME,
        query_vector=query_vector,
        limit=limit,
        query_filter=qdrant_filter,
    )

    return search_result
