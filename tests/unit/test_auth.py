import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Import the actual router under test
from app.api.v1.routers.auth_router import router as auth_router
from app.core.auth import get_current_user


# ---- Test app setup (mount the real router) ----
@pytest.fixture(scope="session")
def app() -> FastAPI:
    app = FastAPI()
    app.include_router(auth_router, prefix="/api/v1")
    app.dependency_overrides[get_current_user] = lambda: type(
        "U",
        (),
        {
            "id": 1,
            "email": "brian@example.com",
            "username": "brian",
            "is_active": True,
            "is_admin": True,
        },
    )()
    return app


@pytest.fixture()
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


# ---- In-memory fakes to avoid DB/psycopg ----
class _FakeUser:
    def __init__(self, id: int, email: str, username: str, hashed_password: str):
        self.id = id
        self.email = email
        self.username = username
        self.hashed_password = hashed_password
        self.is_active = True


class _TokenRow:
    def __init__(self, user_id: int, token_hash: str, revoked: bool = False):
        self.user_id = user_id
        self.token_hash = token_hash
        self.revoked = revoked


@pytest.fixture()
def fake_state():
    """
    Shared fake state for each test: users & refresh tokens table.
    """
    return {
        "users": {
            # password will be "secret" (we'll monkeypatch verify_password to accept it)
            "brian@example.com": _FakeUser(
                id=1,
                email="brian@example.com",
                username="brian",
                hashed_password="hashed-secret",
            ),
            "brian": _FakeUser(
                id=1,
                email="brian@example.com",
                username="brian",
                hashed_password="hashed-secret",
            ),
        },
        "refresh_tokens": {},  # token_hash -> _TokenRow
        "issued_access_tokens": [],
        "last_raw_refresh": None,
    }


# ---- Monkeypatch the dependencies used inside the router ----
@pytest.fixture(autouse=True)
def patch_dependencies(monkeypatch, fake_state):
    # 1) get_db dependency -> return a dummy object (not used by our fakes)
    from app.api.v1.routers import auth_router as ar

    def _fake_get_db():
        yield None

    monkeypatch.setattr(ar, "get_db", _fake_get_db)

    # 2) Security helpers
    # create_access_token -> deterministic token for assertions
    def _fake_create_access_token(subject: str, extra: dict | None = None):
        token = f"access-{subject}"
        fake_state["issued_access_tokens"].append(token)
        return token

    monkeypatch.setattr(ar, "create_access_token", _fake_create_access_token)

    # verify_password -> accept "secret" only
    def _fake_verify_password(plain: str, hashed: str) -> bool:
        return plain == "secret" and hashed == "hashed-secret"

    monkeypatch.setattr(ar, "verify_password", _fake_verify_password)

    # 3) User repository functions
    def _fake_get_user_by_login(db, identifier: str):
        return fake_state["users"].get(identifier)

    def _fake_get_user_by_email(db, email: str):
        return fake_state["users"].get(email)

    def _fake_create_user(db, user_in):
        # Minimal shape to satisfy response_model in /register if you later test it
        u = _FakeUser(
            id=2,
            email=user_in.email,
            username=user_in.username or user_in.email,
            hashed_password="hashed-secret",
        )
        fake_state["users"][u.email] = u
        fake_state["users"][u.username] = u
        return u

    # Patch functions on the actual user_repository module used by the router
    from app.repositories import user_repository as ur

    monkeypatch.setattr(ur, "get_user_by_login", _fake_get_user_by_login, raising=False)
    monkeypatch.setattr(ur, "get_user_by_email", _fake_get_user_by_email, raising=False)
    monkeypatch.setattr(ur, "create_user", _fake_create_user, raising=False)

    # Also patch directly on the router module (covers 'from ... import foo' style)
    monkeypatch.setattr(ar, "get_user_by_login", _fake_get_user_by_login, raising=False)
    monkeypatch.setattr(ar, "get_user_by_email", _fake_get_user_by_email, raising=False)
    monkeypatch.setattr(ar, "create_user", _fake_create_user, raising=False)

    # 4) RefreshTokenRepository methods
    import hashlib

    class _FakeRefreshRepo:
        @staticmethod
        def create(
            db, user_id: int, token_hash: str, expires_at, user_agent=None, ip=None
        ):
            fake_state["refresh_tokens"][token_hash] = _TokenRow(
                user_id=user_id, token_hash=token_hash
            )
            return True

        @staticmethod
        def get_valid(db, token_hash: str):
            row = fake_state["refresh_tokens"].get(token_hash)
            if row and not row.revoked:
                return row
            return None

        @staticmethod
        def revoke(db, token_hash: str):
            row = fake_state["refresh_tokens"].get(token_hash)
            if row:
                row.revoked = True
            return True

    # Patch the whole repository class reference used by the router
    from app.api.v1.routers import auth_router as ar2

    monkeypatch.setattr(ar2, "RefreshTokenRepository", _FakeRefreshRepo)

    def _fake_token_urlsafe(n: int):
        # simulate different tokens on subsequent calls
        count = len(fake_state["refresh_tokens"])
        raw = f"refresh-raw-{count+1}"
        # Store last raw for convenience in tests
        fake_state["last_raw_refresh"] = raw
        return raw

    monkeypatch.setattr(ar2.secrets, "token_urlsafe", _fake_token_urlsafe)

    # Ensure hashlib available to tests (already imported in router)
    assert hasattr(hashlib, "sha256")


# -------------------- TESTS --------------------


def test_login_json_returns_access_and_refresh(client: TestClient, fake_state):
    payload = {"email": "brian@example.com", "password": "secret"}
    res = client.post("/api/v1/auth/login-json", json=payload)
    assert res.status_code == 200
    data = res.json()
    # Access token fields
    assert "access_token" in data and data["access_token"].startswith("access-")
    assert data["token_type"] == "bearer"
    assert "expires_in" in data
    # Refresh token present and stored (hashed) in fake repo
    assert "refresh_token" in data
    assert fake_state["last_raw_refresh"] == data["refresh_token"]


def test_login_form_returns_access_and_refresh(client: TestClient, fake_state):
    form = {"username": "brian", "password": "secret"}
    res = client.post("/api/v1/auth/login", data=form)
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert "refresh_token" in data


def test_login_invalid_credentials(client: TestClient):
    # wrong password
    res = client.post(
        "/api/v1/auth/login-json",
        json={"email": "brian@example.com", "password": "WRONG"},
    )
    assert res.status_code == 401
    assert res.json()["detail"] == "Invalid credentials"


def test_refresh_issues_new_pair_and_rotates(client: TestClient, fake_state):
    # 1) login to get first refresh
    res = client.post(
        "/api/v1/auth/login-json",
        json={"email": "brian@example.com", "password": "secret"},
    )
    assert res.status_code == 200
    first = res.json()
    old_refresh = first["refresh_token"]

    # 2) use refresh to rotate
    res2 = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert res2.status_code == 200
    rotated = res2.json()

    assert rotated["access_token"].startswith("access-")
    assert rotated["refresh_token"] != old_refresh  # rotation happened

    # 3) the old refresh is now invalid
    res3 = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert res3.status_code == 401
    assert res3.json()["detail"] == "Invalid or expired refresh token"


def test_refresh_with_invalid_token(client: TestClient):
    res = client.post("/api/v1/auth/refresh", json={"refresh_token": "does-not-exist"})
    assert res.status_code == 401
    assert res.json()["detail"] == "Invalid or expired refresh token"


def test_me_returns_current_user(client: TestClient):
    res = client.get("/api/v1/auth/me")
    assert res.status_code == 200
    data = res.json()
    assert data["email"] == "brian@example.com"
    assert data["username"] == "brian"
    assert data["is_admin"] is True
