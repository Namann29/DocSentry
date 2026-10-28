import os
import tempfile
from pathlib import Path

import pytest

_tmp = Path(tempfile.mkdtemp())
os.environ["DATABASE_URL"] = f"sqlite:///{(_tmp / 'test.db').as_posix()}"
os.environ["STORAGE_DIR"] = str(_tmp / "storage")
os.environ["ADMIN_PASSWORD"] = "AdminPass123!"
os.environ["ADMIN_EMAIL"] = "admin@docsentry.local"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app, init_db  # noqa: E402


@pytest.fixture(scope="session")
def client():
    init_db()
    with TestClient(app) as c:
        yield c


def login(client: TestClient, email: str, password: str) -> dict:
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="session")
def admin(client):
    return login(client, "admin@docsentry.local", "AdminPass123!")


@pytest.fixture(scope="session")
def users(client, admin):
    out = {"admin": admin}
    for role in ("analyst", "reviewer", "viewer"):
        email = f"{role}@test.local"
        client.post("/api/auth/users", headers=admin, json={"email": email, "password": "Password123!x", "role": role})
        out[role] = login(client, email, "Password123!x")
    email = "analyst2@test.local"
    client.post("/api/auth/users", headers=admin, json={"email": email, "password": "Password123!x", "role": "analyst"})
    out["analyst2"] = login(client, email, "Password123!x")
    return out