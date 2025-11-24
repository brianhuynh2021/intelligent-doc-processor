import os
import sys

# Thêm project root vào sys.path
CURRENT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
sys.path.insert(0, PROJECT_ROOT)

from app.core.config import app_config
from infra.vector_store.qdrant_vector_store import QdrantVectorStore


def main():
    store = QdrantVectorStore()

    dim = app_config.EMBEDDING_DIM
    vec = [0.1] * dim
    payload = {
        "doc_id": "test-doc-1",
        "page": 1,
        "source": "manual",
        "workspace_id": "ws-123",
    }

    print("Upsert:")
    ids = store.upsert([vec], [payload])
    print(ids)

    print("Search:")
    res = store.search(vec, limit=3, filters={"workspace_id": "ws-123"})
    print(res)

    print("Delete:")
    store.delete_by_ids(ids)


if __name__ == "__main__":
    main()