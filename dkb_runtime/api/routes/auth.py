from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm

from dkb_runtime.api.middleware.auth import create_access_token
from dkb_runtime.core.config import get_settings

router = APIRouter()


@router.post("/token")
def issue_access_token(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]) -> dict[str, str]:
    s = get_settings()
    if not s.dkb_admin_user or not s.dkb_admin_password:
        raise HTTPException(status_code=503, detail="Admin credentials not configured")
    if form_data.username != s.dkb_admin_user or form_data.password != s.dkb_admin_password:
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    token = create_access_token({"sub": form_data.username})
    return {"access_token": token, "token_type": "bearer"}
