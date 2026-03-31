from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from dkb_runtime.core.config import get_settings

_bearer = HTTPBearer(auto_error=False)


def create_access_token(data: dict[str, Any]) -> str:
    settings = get_settings()
    if not settings.dkb_jwt_secret:
        raise HTTPException(status_code=503, detail="JWT secret not configured")
    to_encode = {**data}
    expire = datetime.now(UTC) + timedelta(minutes=settings.dkb_jwt_expire_minutes)
    to_encode["exp"] = expire
    return jwt.encode(to_encode, settings.dkb_jwt_secret, algorithm=settings.dkb_jwt_algorithm)


def verify_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    if not settings.dkb_jwt_secret:
        raise HTTPException(status_code=503, detail="JWT secret not configured")
    try:
        return jwt.decode(token, settings.dkb_jwt_secret, algorithms=[settings.dkb_jwt_algorithm])
    except JWTError as e:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from e


def try_verify_request_token(authorization: str | None) -> dict[str, Any] | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization[7:].strip()
    if not token:
        return None
    try:
        return verify_token(token)
    except HTTPException:
        return None


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> dict[str, Any]:
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return verify_token(credentials.credentials)
