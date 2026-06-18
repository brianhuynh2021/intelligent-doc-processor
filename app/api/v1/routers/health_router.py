from __future__ import annotations

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.core.config import settings
from app.core.database import engine

router = APIRouter()


def _check_db() -> tuple[bool, str]:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1")).scalar()
        return True, "connected"
    except Exception as e:  # pragma: no cover - depends on live DB
        return False, str(e)


def _check_redis() -> tuple[bool, str]:
    try:
        import redis  # type: ignore

        client = redis.from_url(settings.REDIS_URL, socket_connect_timeout=1)
        client.ping()
        return True, "connected"
    except Exception as e:  # pragma: no cover
        return False, str(e)


def _check_qdrant() -> tuple[bool, str]:
    try:
        from infra.vector_store.qdrant_vector_store import QdrantVectorStore

        if QdrantVectorStore().ping():
            return True, "connected"
        return False, "unhealthy"
    except Exception as e:  # pragma: no cover
        return False, str(e)


@router.get("/health", tags=["Health"])
def health():
    """Full health check with per-dependency status (human-readable)."""
    db_ok, db_msg = _check_db()
    return {
        "app": "healthy",
        "database": "connected ✅" if db_ok else f"failed ❌: {db_msg}",
    }


@router.get("/health/live", tags=["Health"])
def liveness():
    """Liveness probe: process is up. No dependency checks — k8s restarts the
    pod only if this fails."""
    return {"status": "alive"}


@router.get("/health/ready", tags=["Health"])
def readiness(response: Response):
    """Readiness probe: can serve traffic. Checks critical dependencies and
    returns 503 if any required one is down so k8s stops routing to it."""
    checks = {
        "database": _check_db(),
        "redis": _check_redis(),
        "qdrant": _check_qdrant(),
    }
    # DB is required; redis/qdrant degrade gracefully (cache miss / no vectors)
    required_ok = checks["database"][0]
    body = {
        "status": "ready" if required_ok else "not_ready",
        "checks": {
            name: ("ok" if ok else f"down: {msg}") for name, (ok, msg) in checks.items()
        },
    }
    if not required_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return body


@router.get("/health/qdrant", tags=["Health"])
def qdrant_health():
    """Qdrant health check only"""
    ok, msg = _check_qdrant()
    return {"qdrant": "connected ✅" if ok else f"failed ❌: {msg}"}
