import logging
from typing import Any, Dict, List
from uuid import uuid4

from qdrant_client.http.models import (
    FieldCondition,
    Filter,
    MatchValue,
    PointIdsList,
    PointStruct,
)

from app.core.config import app_config
from infra.vector_store.interfaces import VectorStore
from infra.vector_store.qdrant_client import ensure_qdrant_collection, get_qdrant_client

logger = logging.getLogger(__name__)


class VectorStoreError(Exception):
    """Custom exception for vector store operations."""

    pass


class QdrantVectorStore(VectorStore):
    """
    Qdrant implementation of the VectorStore interface.

    This class encapsulates all Qdrant interactions behind a
    clean API, allowing the application to remain implementation-agnostic.
    """

    def __init__(self) -> None:
        # Ensure collection exists when the store is initialized
        ensure_qdrant_collection()
        self.client = get_qdrant_client()
        self.collection = app_config.QDRANT_COLLECTION

    def upsert(
        self,
        vectors: List[List[float]],
        payloads: List[Dict[str, Any]],
    ) -> List[str]:
        """
        Insert or update vectors in Qdrant with associated metadata.

        Returns:
            List of generated UUIDs.
        """
        if len(vectors) != len(payloads):
            raise ValueError("Vectors and payloads must have the same length")

        try:
            ids = [str(uuid4()) for _ in vectors]

            points = [
                PointStruct(
                    id=id_,
                    vector=vec,
                    payload=pl,
                )
                for id_, vec, pl in zip(ids, vectors, payloads)
            ]

            self.client.upsert(
                collection_name=self.collection,
                points=points,
            )

            return ids

        except Exception as exc:
            logger.exception("Failed to upsert vectors")
            raise VectorStoreError("Failed to upsert vectors") from exc

    def search(
        self,
        query_vector: List[float],
        limit: int = 5,
        filters: Dict[str, Any] | None = None,
    ) -> List[Dict[str, Any]]:
        """
        Perform a similarity search in Qdrant.

        Returns:
            A list of dictionaries containing:
                - "id"
                - "score"
                - "payload"
        """
        try:
            qdrant_filter: Filter | None = None

            # Convert filters (dict) to Qdrant Filter object
            if filters:
                conditions = []
                for field, value in filters.items():
                    conditions.append(
                        FieldCondition(
                            key=field,
                            match=MatchValue(value=value),
                        )
                    )
                qdrant_filter = Filter(must=conditions)

            results = self.client.search(
                collection_name=self.collection,
                query_vector=query_vector,
                limit=limit,
                query_filter=qdrant_filter,
            )

            return [
                {
                    "id": str(point.id),
                    "score": point.score,
                    "payload": point.payload or {},
                }
                for point in results
            ]

        except Exception as exc:
            logger.exception("Failed to search Qdrant")
            raise VectorStoreError("Search operation failed") from exc

    def delete_by_ids(self, ids: List[str]) -> None:
        """
        Delete vectors by their point IDs.
        """
        if not ids:
            return

        try:
            self.client.delete(
                collection_name=self.collection,
                points_selector=PointIdsList(points=ids),
            )

        except Exception as exc:
            logger.exception("Failed to delete vectors")
            raise VectorStoreError("Delete operation failed") from exc

    def ping(self) -> bool:
        """
        Returns True if Qdrant is reachable, False otherwise.
        """
        try:
            self.client.get_collections()
            return True
        except Exception:
            return False
