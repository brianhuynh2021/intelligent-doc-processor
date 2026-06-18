"""Tests for liveness/readiness probes and metrics endpoint."""
from fastapi.testclient import TestClient

from app.api.v1.routers import health_router
from app.main import app

client = TestClient(app)


def test_liveness_always_ok():
    r = client.get("/api/v1/health/live")
    assert r.status_code == 200
    assert r.json() == {"status": "alive"}


def test_readiness_ok_when_db_up(monkeypatch):
    monkeypatch.setattr(health_router, "_check_db", lambda: (True, "connected"))
    monkeypatch.setattr(health_router, "_check_redis", lambda: (True, "connected"))
    monkeypatch.setattr(health_router, "_check_qdrant", lambda: (True, "connected"))
    r = client.get("/api/v1/health/ready")
    assert r.status_code == 200
    assert r.json()["status"] == "ready"


def test_readiness_503_when_db_down(monkeypatch):
    monkeypatch.setattr(health_router, "_check_db", lambda: (False, "boom"))
    monkeypatch.setattr(health_router, "_check_redis", lambda: (True, "connected"))
    monkeypatch.setattr(health_router, "_check_qdrant", lambda: (True, "connected"))
    r = client.get("/api/v1/health/ready")
    assert r.status_code == 503
    assert r.json()["status"] == "not_ready"
    assert "down" in r.json()["checks"]["database"]


def test_metrics_endpoint_exposes_prometheus():
    client.get("/health")  # generate some traffic
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "http_requests" in r.text
