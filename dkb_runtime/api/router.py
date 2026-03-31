from __future__ import annotations

from fastapi import APIRouter, FastAPI

from dkb_runtime.api.routes import directives, health, packs, scoring, search, similarity, sources, verdict


def register_dashboard_routes(app: FastAPI) -> None:
    """Mount HTML dashboard at `/dashboard` (no API prefix)."""
    from dkb_runtime.web.dashboard import router as dashboard_router

    app.include_router(dashboard_router)


api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(sources.router, prefix="/sources", tags=["sources"])
api_router.include_router(similarity.router, prefix="/directives", tags=["similarity"])
api_router.include_router(directives.router, prefix="/directives", tags=["directives"])
api_router.include_router(search.router, prefix="/search", tags=["search"])
api_router.include_router(scoring.router, prefix="/scoring", tags=["scoring"])
api_router.include_router(verdict.router, prefix="/verdict", tags=["verdict"])
api_router.include_router(packs.router, prefix="/packs", tags=["packs"])
