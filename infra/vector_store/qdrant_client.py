from functools import lru_cache

from qdrant_client import QdrantClient
from qdrant_client.http import models as rest

from app.core.config import settings


@lru_cache
def get_qdrant_client() -> QdrantClient:
    """
    Create and cache a single QdrantClient instance.
    """
    return QdrantClient(
        url=settings.QDRANT_URL,
        timeout=5.0,
    )


def ensure_qdrant_collection() -> None:
    """
    Ensure the Qdrant collection exists with the correct vector configuration.
    Payload schema sẽ để Qdrant tự xử lý (schemaless), không cần PayloadSchema.
    """
    client = get_qdrant_client()
    collection_name = settings.QDRANT_COLLECTION

    try:
        if client.collection_exists(collection_name):
            return
    except Exception:
        existing = [c.name for c in client.get_collections().collections]
        if collection_name in existing:
            return

    # Tạo collection với vector params
    client.create_collection(
        collection_name=collection_name,
        vectors_config=rest.VectorParams(
            size=settings.EMBEDDING_DIM,
            distance=rest.Distance.COSINE,
        ),
    )
