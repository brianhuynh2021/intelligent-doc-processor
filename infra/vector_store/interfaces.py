from abc import ABC, abstractmethod
from typing import Any, Dict, List


class VectorStore(ABC):
    """
    Abstract interface for any vector store backend.

    By defining a clean interface, the rest of the application
    becomes independent of the concrete implementation (Qdrant, Pinecone,
    Weaviate, Milvus, or even a simple in-memory index).

    This follows SOLID principles (Dependency Inversion),
    making the system modular, testable, and easy to extend.
    """

    @abstractmethod
    def upsert(
        self,
        vectors: List[List[float]],
        payloads: List[Dict[str, Any]],
    ) -> List[str]:
        """
        Insert or update multiple vectors with their metadata.

        Parameters:
            vectors: List of embedding vectors.
            payloads: List of metadata dictionaries for each vector.

        Returns:
            List of generated or assigned vector IDs.
        """
        ...

    @abstractmethod
    def search(
        self,
        query_vector: List[float],
        limit: int = 5,
        filters: Dict[str, Any] | None = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for the most similar vectors to a given query vector.

        Parameters:
            query_vector: The embedding to compare against.
            limit: Maximum number of results to return.
            filters: Optional metadata filters (e.g., workspace_id).

        Returns:
            List of dictionaries containing:
                - id: vector ID
                - score: similarity score
                - payload: associated metadata
        """
        ...

    @abstractmethod
    def delete_by_ids(self, ids: List[str]) -> None:
        """
        Delete multiple vectors by their IDs.

        Parameters:
            ids: List of vector IDs to delete.
        """
        ...

    @abstractmethod
    def ping(self) -> bool:
        """
        Health check to verify that the vector store is reachable.

        Returns:
            True if operational, otherwise False.
        """
        ...
