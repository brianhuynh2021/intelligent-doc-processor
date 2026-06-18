"""Integration test for the API key lifecycle: create → list → revoke,
plus resolving a key back to its owner (the X-API-Key auth path)."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.auth import get_current_user
from app.core.database import get_db
from app.main import app
from app.models import Base
from app.models.api_key_model import ApiKey
from app.models.user_model import User
from app.services.api_key_service import resolve_api_key


@pytest.fixture()
def test_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine, tables=[User.__table__, ApiKey.__table__])

    db = TestingSessionLocal()
    user = User(
        email="k@example.com",
        username="keyuser",
        hashed_password="x",
        is_active=True,
        role="user",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    user_id = user.id
    db.close()

    def override_get_db():
        d = TestingSessionLocal()
        try:
            yield d
        finally:
            d.close()

    def override_user():
        d = TestingSessionLocal()
        try:
            return d.query(User).filter(User.id == user_id).first()
        finally:
            d.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_user
    yield TestingSessionLocal, user_id
    app.dependency_overrides.clear()
    engine.dispose()


@pytest.fixture()
def client(test_db):
    return TestClient(app)


def test_api_key_lifecycle(client, test_db):
    SessionLocal, user_id = test_db

    # create
    r = client.post("/api/v1/api-keys", json={"name": "ci-key"})
    assert r.status_code == 201
    created = r.json()
    plaintext = created["plaintext_key"]
    assert plaintext.startswith("dpk_")
    key_id = created["id"]
    assert created["key_prefix"] == plaintext[:12]

    # list shows it (without plaintext)
    r = client.get("/api/v1/api-keys")
    assert r.status_code == 200
    keys = r.json()
    assert len(keys) == 1
    assert "plaintext_key" not in keys[0]

    # resolve the plaintext back to the owning user
    db = SessionLocal()
    try:
        resolved = resolve_api_key(db, plaintext)
        assert resolved is not None and resolved.id == user_id
        assert resolve_api_key(db, "dpk_wrongwrongwrong") is None
    finally:
        db.close()

    # revoke
    r = client.delete(f"/api/v1/api-keys/{key_id}")
    assert r.status_code == 204

    # revoked key no longer resolves
    db = SessionLocal()
    try:
        assert resolve_api_key(db, plaintext) is None
    finally:
        db.close()

    # second revoke → 404
    r = client.delete(f"/api/v1/api-keys/{key_id}")
    assert r.status_code == 404
