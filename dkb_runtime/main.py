from __future__ import annotations

from fastapi import FastAPI

from dkb_runtime.api.router import api_router
from dkb_runtime.core.config import get_settings

settings = get_settings()

app = FastAPI(title=settings.app_name, version="0.1.0")
app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/", tags=["root"])
def root() -> dict[str, str]:
    return {"name": settings.app_name, "status": "ok"}
