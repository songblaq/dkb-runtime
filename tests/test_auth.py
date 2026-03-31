from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from dkb_runtime.api.middleware.auth import create_access_token, verify_token
from dkb_runtime.core.config import get_settings
from dkb_runtime.main import app

PREFIX = get_settings().api_v1_prefix


@pytest.fixture
def auth_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DKB_JWT_SECRET", "unit-test-jwt-secret-key-32bytes!")
    monkeypatch.setenv("DKB_ADMIN_USER", "admin")
    monkeypatch.setenv("DKB_ADMIN_PASSWORD", "secret-pass")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def client():
    return TestClient(app)


def test_create_and_verify_token_roundtrip(auth_env: None) -> None:
    token = create_access_token({"sub": "admin"})
    payload = verify_token(token)
    assert payload.get("sub") == "admin"


def test_verify_token_rejects_garbage(auth_env: None) -> None:
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as ei:
        verify_token("not-a-jwt")
    assert ei.value.status_code == 401


def test_token_endpoint_success(auth_env: None, client: TestClient) -> None:
    r = client.post(
        f"{PREFIX}/auth/token",
        data={"username": "admin", "password": "secret-pass"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get("token_type") == "bearer"
    assert "access_token" in body
    s = get_settings()
    claims = jwt.decode(body["access_token"], s.dkb_jwt_secret, algorithms=[s.dkb_jwt_algorithm])
    assert claims["sub"] == "admin"


def test_token_endpoint_wrong_password(auth_env: None, client: TestClient) -> None:
    r = client.post(
        f"{PREFIX}/auth/token",
        data={"username": "admin", "password": "wrong"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 401
    err = r.json()["error"]
    assert err["code"] == "UNAUTHORIZED"


def test_create_directive_without_token_returns_401_structured(client: TestClient) -> None:
    r = client.post(f"{PREFIX}/directives", json={"preferred_name": "x"})
    assert r.status_code == 401
    body = r.json()
    assert "error" in body
    assert body["error"]["code"] == "UNAUTHORIZED"


def test_create_directive_with_token(
    auth_env: None,
    client: TestClient,
    db,
) -> None:
    tr = client.post(
        f"{PREFIX}/auth/token",
        data={"username": "admin", "password": "secret-pass"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert tr.status_code == 200
    tok = tr.json()["access_token"]
    r = client.post(
        f"{PREFIX}/directives",
        json={"preferred_name": "auth-test-directive", "status": "active"},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 201
    assert r.json()["preferred_name"] == "auth-test-directive"
