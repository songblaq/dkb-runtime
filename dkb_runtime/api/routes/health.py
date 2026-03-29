from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from dkb_runtime.api.deps import DbSession

router = APIRouter()


@router.get("/healthz")
def healthz(db: DbSession) -> dict:
    db.execute(text("SELECT 1"))
    return {"status": "ok"}
