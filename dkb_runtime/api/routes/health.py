from __future__ import annotations

import time

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from dkb_runtime.api.deps import DbSession
from dkb_runtime.schemas.health import HealthBasicResponse, HealthLiveResponse, HealthReadyResponse
from dkb_runtime.version import package_version

router = APIRouter()

_FALLBACK_START_MONO = time.monotonic()

DKB_VERSION_HEADER = "X-DKB-Version"


def _set_version_header(response: Response) -> None:
    response.headers[DKB_VERSION_HEADER] = package_version()


@router.get("/health", response_model=HealthBasicResponse)
def health_check(request: Request, response: Response) -> HealthBasicResponse:
    """Return API version and uptime since application startup."""
    _set_version_header(response)
    started = getattr(request.app.state, "started_mono", None)
    if started is None:
        started = _FALLBACK_START_MONO
    uptime = time.monotonic() - started
    return HealthBasicResponse(status="ok", version=package_version(), uptime_seconds=round(uptime, 3))


@router.get("/health/ready", response_model=HealthReadyResponse)
def health_ready(response: Response, db: DbSession) -> HealthReadyResponse:
    """Verify database connectivity; use for orchestration readiness probes."""
    _set_version_header(response)
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as e:
        return JSONResponse(
            status_code=503,
            content={"detail": f"Database not ready: {e!s}"},
            headers={DKB_VERSION_HEADER: package_version()},
        )
    return HealthReadyResponse(status="ready", database="connected")


@router.get("/health/live", response_model=HealthLiveResponse)
def health_live(response: Response) -> HealthLiveResponse:
    """Lightweight liveness probe; does not touch external dependencies."""
    _set_version_header(response)
    return HealthLiveResponse(status="alive")
