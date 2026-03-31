from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


def structured_error(
    code: str,
    message: str,
    *,
    details: Any | None = None,
    status_code: int,
) -> JSONResponse:
    body: dict[str, Any] = {
        "error": {
            "code": code,
            "message": message,
            "details": details,
        }
    }
    return JSONResponse(status_code=status_code, content=body)


def _http_status_to_code(status: int) -> str:
    return {
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        422: "VALIDATION_ERROR",
        429: "RATE_LIMITED",
        500: "INTERNAL_ERROR",
    }.get(status, "HTTP_ERROR")


def _detail_message(detail: Any) -> str:
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list):
        return "; ".join(str(x) for x in detail)
    return str(detail)


async def fastapi_http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    code = _http_status_to_code(exc.status_code)
    msg = _detail_message(exc.detail)
    details = exc.detail if isinstance(exc.detail, (dict, list)) else None
    return structured_error(code, msg, details=details, status_code=exc.status_code)


async def starlette_http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    code = _http_status_to_code(exc.status_code)
    msg = _detail_message(exc.detail)
    return structured_error(code, msg, details=None, status_code=exc.status_code)


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return structured_error(
        "VALIDATION_ERROR",
        "Request validation failed",
        details=exc.errors(),
        status_code=422,
    )


async def rate_limit_exception_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return structured_error(
        "RATE_LIMITED",
        str(exc.detail) if exc.detail else "Rate limit exceeded",
        details=None,
        status_code=429,
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error: %s", exc)
    return structured_error(
        "INTERNAL_ERROR",
        "An unexpected error occurred",
        details=None,
        status_code=500,
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(HTTPException, fastapi_http_exception_handler)
    app.add_exception_handler(StarletteHTTPException, starlette_http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(RateLimitExceeded, rate_limit_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
