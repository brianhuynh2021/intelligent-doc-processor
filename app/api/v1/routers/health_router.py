from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from app.core.database import engine

router = APIRouter()


@router.get("/health", tags=["Health"])
def health():
    """Health check"""
    status = {"app": "healthy"}
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1")).scalar()
        status["database"] = "connected ✅"
    except Exception as e:
        status["database"] = f"failed ❌: {e}"
    return status


@router.get("/health/qdrant", tags=["Health"])
def qdrant_health():
    """Qdrant health check only"""
    try:
        from infra.vector_store.qdrant_vector_store import QdrantVectorStore
    except ModuleNotFoundError as e:
        return {"qdrant": f"dependency missing ❌: {e}"}

    try:
        qdrant_store = QdrantVectorStore()
        if qdrant_store.ping():
            return {"qdrant": "connected ✅"}
        return {"qdrant": "unhealthy ❌"}
    except Exception as e:
        return {"qdrant": f"failed ❌: {e}"}
