from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from dkb_runtime.core.config import get_settings
from dkb_runtime.db.session import get_db
from dkb_runtime.main import app
from dkb_runtime.version import package_version

PREFIX = get_settings().api_v1_prefix
DKB_VERSION_HEADER = "X-DKB-Version"


@pytest.fixture
def client():
    return TestClient(app)


def test_health_live_returns_200_and_header(client: TestClient):
    r = client.get(f"{PREFIX}/health/live")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "alive"
    assert r.headers.get(DKB_VERSION_HEADER) == package_version()


def test_health_basic_returns_version_uptime_and_header(client: TestClient):
    r = client.get(f"{PREFIX}/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["version"] == package_version()
    assert isinstance(data["uptime_seconds"], (int, float))
    assert data["uptime_seconds"] >= 0
    assert r.headers.get(DKB_VERSION_HEADER) == package_version()


@pytest.mark.usefixtures("engine")
def test_health_ready_ok(client: TestClient):
    r = client.get(f"{PREFIX}/health/ready")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ready"
    assert data["database"] == "connected"
    assert r.headers.get(DKB_VERSION_HEADER) == package_version()


def test_health_ready_503_when_db_unavailable(client: TestClient):
    class _BadSession:
        def execute(self, *_args, **_kwargs):
            raise OperationalError("SELECT 1", {}, orig=Exception("connection refused"))

    def _bad_get_db():
        yield _BadSession()

    app.dependency_overrides[get_db] = _bad_get_db
    try:
        r = client.get(f"{PREFIX}/health/ready")
        assert r.status_code == 503
        assert r.headers.get(DKB_VERSION_HEADER) == package_version()
    finally:
        app.dependency_overrides.clear()
