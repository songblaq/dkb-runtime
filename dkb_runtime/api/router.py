from __future__ import annotations

from fastapi import APIRouter, FastAPI

from dkb_runtime.api.routes import concept, directives, health, packs, scoring, search, similarity, sources, verdict


def register_dashboard_routes(app: FastAPI) -> None:
    """Mount HTML dashboard at `/dashboard` (no API prefix)."""
    from dkb_runtime.web.dashboard import router as dashboard_router

    app.include_router(dashboard_router)


api_router = APIRouter()
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(sources.router, prefix="/sources", tags=["Sources"])
api_router.include_router(similarity.router, prefix="/directives", tags=["Similarity"])
api_router.include_router(concept.router, prefix="/directives", tags=["Concepts"])
api_router.include_router(directives.router, prefix="/directives", tags=["Directives"])
api_router.include_router(search.router, prefix="/search", tags=["Search"])
api_router.include_router(scoring.router, prefix="/scoring", tags=["Scoring"])
api_router.include_router(verdict.router, prefix="/verdict", tags=["Verdict"])
api_router.include_router(packs.router, prefix="/packs", tags=["Packs"])
