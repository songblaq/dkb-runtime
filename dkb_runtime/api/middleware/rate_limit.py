from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import FastAPI, Request
from slowapi import Limiter
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware

from dkb_runtime.api.middleware.auth import try_verify_request_token
from dkb_runtime.api.middleware.error_handler import structured_error

_ANON_LIMIT = 20
_AUTH_LIMIT = 100
_WINDOW_SEC = 60

_tier_windows: dict[str, deque[float]] = defaultdict(deque)


def rate_limit_identity(request: Request) -> str:
    auth = request.headers.get("Authorization")
    payload = try_verify_request_token(auth)
    if payload is not None and payload.get("sub"):
        return f"u:{payload['sub']}"
    return f"a:{get_remote_address(request)}"


def _tier_limit_for_key(key: str) -> int:
    return _AUTH_LIMIT if key.startswith("u:") else _ANON_LIMIT


def _tiered_allow(key: str) -> bool:
    now = time.monotonic()
    window = _tier_windows[key]
    cutoff = now - _WINDOW_SEC
    while window and window[0] < cutoff:
        window.popleft()
    limit = _tier_limit_for_key(key)
    if len(window) >= limit:
        return False
    window.append(now)
    return True


class TieredRateLimitMiddleware(BaseHTTPMiddleware):
    """20 req/min without a valid JWT; 100 req/min with a valid JWT."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path.startswith("/docs") or path.startswith("/redoc") or path in ("/openapi.json", "/favicon.ico"):
            return await call_next(request)

        key = rate_limit_identity(request)
        if not _tiered_allow(key):
            return structured_error(
                "RATE_LIMITED",
                "Rate limit exceeded",
                details={"limit_per_minute": _tier_limit_for_key(key), "window_seconds": _WINDOW_SEC},
                status_code=429,
            )
        return await call_next(request)


limiter = Limiter(key_func=rate_limit_identity, default_limits=[])


def register_rate_limiting(app: FastAPI) -> None:
    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(TieredRateLimitMiddleware)


def clear_rate_limit_state_for_tests() -> None:
    _tier_windows.clear()
    storage = getattr(limiter, "_storage", None)
    if storage is not None and hasattr(storage, "clear"):
        storage.clear()
