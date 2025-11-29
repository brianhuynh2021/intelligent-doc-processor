"""
Indexing pipeline for document chunks.

Takes cleaned text chunks + metadata:
- generates embeddings (with Redis cache)
- stores them in Qdrant for later retrieval
"""

from typing import Any, Dict, List

from app.services.embedding_service import embed_with_cache
from app.services.vector_store import upsert_embeddings


def index_chunks(
    chunks: List[Dict[str, Any]],
) -> None:
    """
    Index a list of chunks into the vector store.

    Expected chunk structure (you can adapt fields to your real code):

    chunk = {
        "id": str,             # unique id, e.g. "fileid_page_chunk"
        "text": str,           # chunk text
        "file_id": str,        # original file/document id
        "page": int,           # page number (optional)
        "chunk_index": int,    # index inside the page (optional)
        ...
    }
    """
    if not chunks:
        return

    # 1. Extract ids, texts, metadata
    ids: List[str] = []
    texts: List[str] = []
    metadatas: List[Dict[str, Any]] = []

    for c in chunks:
        # adjust these keys to your real chunk structure
        ids.append(c["id"])
        texts.append(c["text"])

        metadata = {
            "file_id": c.get("file_id"),
            "document_id": c.get("document_id"),
            "owner_id": c.get("document_owner_id") or c.get("owner_id"),
            "page": c.get("page"),
            "chunk_index": c.get("chunk_index"),
            "content_type": c.get("content_type"),
            "document_created_at": c.get("document_created_at"),
            "document_created_at_ts": c.get("document_created_at_ts"),
            "text": c["text"],
        }
        metadatas.append(metadata)

    # 2. Generate embeddings (with Redis cache)
    vectors = embed_with_cache(texts)

    # 3. Upsert into Qdrant
    upsert_embeddings(ids=ids, vectors=vectors, metadatas=metadatas)
