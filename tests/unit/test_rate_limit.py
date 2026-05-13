from __future__ import annotations

from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from slowapi.middleware import SlowAPIMiddleware

from app.core.exception_handlers import register_exception_handlers
from app.core.rate_limit import limiter


def _make_app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)
    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        rid = request.headers.get("X-Request-ID") or str(uuid4())
        request.state.request_id = rid
        response = await call_next(request)
        response.headers.setdefault("X-Request-ID", rid)
        return response

    @app.get("/limited")
    @limiter.limit("2/minute")
    async def limited(request: Request):
        return {"ok": True}

    return app


def test_rate_limit_returns_structured_429():
    client = TestClient(_make_app())

    assert client.get("/limited").status_code == 200
    assert client.get("/limited").status_code == 200

    resp = client.get("/limited")
    assert resp.status_code == 429
    data = resp.json()
    assert data["success"] is False
    assert data["error"]["code"] == "rate_limited"
    assert data["error"]["message"] == "Rate limit exceeded"
    assert data["request_id"]
