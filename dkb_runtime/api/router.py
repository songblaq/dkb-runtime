from __future__ import annotations

from fastapi import APIRouter

from dkb_runtime.api.routes import directives, health, search, sources

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(sources.router, prefix="/sources", tags=["sources"])
api_router.include_router(directives.router, prefix="/directives", tags=["directives"])
api_router.include_router(search.router, prefix="/search", tags=["search"])
