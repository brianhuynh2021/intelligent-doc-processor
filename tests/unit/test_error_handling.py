from __future__ import annotations

from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from app.core.errors import NotFoundError
from app.core.exception_handlers import register_exception_handlers


def _make_app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        rid = request.headers.get("X-Request-ID") or str(uuid4())
        request.state.request_id = rid
        response = await call_next(request)
        response.headers.setdefault("X-Request-ID", rid)
        return response

    class EchoIn(BaseModel):
        query: str = Field(..., min_length=1)

    @app.post("/echo")
    def echo(body: EchoIn):
        return {"query": body.query}

    @app.get("/http")
    def http_error():
        raise HTTPException(status_code=404, detail="Missing")

    @app.get("/app")
    def app_error():
        raise NotFoundError("Nope")

    @app.get("/boom")
    def boom():
        raise RuntimeError("explode")

    return app


def test_validation_error_is_structured():
    client = TestClient(_make_app())
    resp = client.post("/echo", json={"query": ""})
    assert resp.status_code == 422
    data = resp.json()
    assert data["success"] is False
    assert data["error"]["code"] == "validation_error"
    assert data["request_id"]
    assert resp.headers.get("X-Request-ID") == data["request_id"]


def test_http_exception_is_structured():
    client = TestClient(_make_app())
    resp = client.get("/http")
    assert resp.status_code == 404
    data = resp.json()
    assert data["error"]["code"] == "not_found"
    assert data["error"]["message"] == "Missing"
    assert data["request_id"]


def test_app_error_is_structured():
    client = TestClient(_make_app())
    resp = client.get("/app")
    assert resp.status_code == 404
    data = resp.json()
    assert data["error"]["code"] == "not_found"
    assert data["error"]["message"] == "Nope"


def test_unhandled_exception_is_structured():
    client = TestClient(_make_app(), raise_server_exceptions=False)
    resp = client.get("/boom")
    assert resp.status_code == 500
    data = resp.json()
    assert data["error"]["code"] == "internal_error"
    assert data["request_id"]
