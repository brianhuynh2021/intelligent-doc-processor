import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import time
from typing import Any, Dict, List

from app.services.indexing_pipeline import index_chunks
from app.services.embedding_service import embed_with_cache
from app.services.vector_store import search_similar


def build_fake_chunks() -> List[Dict[str, Any]]:
    # Demo: 3 chunks giả lập cho 1 file
    file_id = "demo-file-1"

    texts = [
        "FastAPI is a modern, fast web framework for building APIs with Python.",
        "Qdrant is a vector database for embeddings and semantic search.",
        "Redis can be used as a cache layer to speed up embedding generation.",
    ]

    chunks: List[Dict[str, Any]] = []
    for i, text in enumerate(texts):
        chunks.append(
            {
                "id": f"{file_id}_page1_chunk{i}",
                "text": text,
                "file_id": file_id,
                "page": 1,
                "chunk_index": i,
            }
        )
    return chunks


def main():
    chunks = build_fake_chunks()

    print("Indexing chunks...")
    t0 = time.perf_counter()
    index_chunks(chunks)
    t1 = time.perf_counter()
    print(f"Indexed {len(chunks)} chunks in {t1 - t0:.3f} seconds")

    # Test search
    query = "How to build APIs with Python?"
    print(f"\nSearching for: {query!r}")
    query_vec = embed_with_cache([query])[0]

    results = search_similar(query_vector=query_vec, limit=3)

    print("\nTop results:")
    for r in results:
        payload = r.payload or {}
        score = r.score
        text = payload.get("text")
        file_id = payload.get("file_id")
        page = payload.get("page")
        chunk_index = payload.get("chunk_index")

        print(f"- score={score:.4f} file_id={file_id} page={page} chunk={chunk_index}")
        print(f"  text: {text}")
        print()

    print("Done.")


if __name__ == "__main__":
    main()