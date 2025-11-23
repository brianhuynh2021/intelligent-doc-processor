from functools import lru_cache

from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    Distance,
    PayloadSchema,
    PayloadSchemaType,
    VectorParams,
)

from app.core.config import app_config


@lru_cache
def get_qdrant_client() -> QdrantClient:
    """
    Creates and caches a single QdrantClient instance.

    Using LRU cache ensures that:
    - only one client is created
    - all modules reuse the same connection
    - startup time and overhead are minimized
    """
    return QdrantClient(
        url=app_config.QDRANT_URL,
        api_key=getattr(app_config, "QDRANT_API_KEY", None),
        timeout=5.0,
    )


def ensure_qdrant_collection() -> None:
    """
    Verify that the configured Qdrant collection exists.
    If it does not exist, create it with:
    - correct vector dimension
    - cosine distance metric
    - metadata (payload) schema
    """
    client = get_qdrant_client()
    collection_name = app_config.QDRANT_COLLECTION

    # Check existing collections
    existing = [c.name for c in client.get_collections().collections]
    if collection_name in existing:
        return  # Already exists, nothing to do

    # Create new collection with schema
    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(
            size=app_config.EMBEDDING_DIM,
            distance=Distance.COSINE,
        ),
        payload_schema=PayloadSchema(
            {
                "doc_id": PayloadSchemaType.KEYWORD,
                "page": PayloadSchemaType.INTEGER,
                "source": PayloadSchemaType.KEYWORD,
                "workspace_id": PayloadSchemaType.KEYWORD,
            }
        ),
    )
