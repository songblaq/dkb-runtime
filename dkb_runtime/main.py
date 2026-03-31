from __future__ import annotations

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel

from dkb_runtime.api.router import api_router, register_dashboard_routes
from dkb_runtime.core.config import get_settings
from dkb_runtime.version import package_version

settings = get_settings()

_API_VERSION = package_version()

_OPENAPI_DESCRIPTION = """
DKB Runtime exposes HTTP APIs for the **Directive Knowledge Base** pipeline: ingesting sources,
canonicalizing directives, multi-dimensional scoring, similarity search, cognitive analytics
(concepts), curated packs, and verdict evaluation.

Typical flow: register **Sources** → capture **Snapshots** → extract **Raw directives** →
**Canonicalize** → **Score** dimensions → **Evaluate** verdicts → assemble **Packs** and **Export**
artifacts for agents and tooling.
""".strip()


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.started_mono = time.monotonic()
    yield


class RootResponse(BaseModel):
    name: str
    status: str

    model_config = {
        "json_schema_extra": {
            "examples": [{"name": "DKB Runtime", "status": "ok"}],
        }
    }


app = FastAPI(
    title="DKB Runtime API",
    description=_OPENAPI_DESCRIPTION,
    version=_API_VERSION,
    lifespan=lifespan,
    openapi_tags=[
        {"name": "Sources", "description": "Source registry, snapshots, and raw directive ingestion."},
        {"name": "Directives", "description": "Canonical directive CRUD and listing."},
        {"name": "Scoring", "description": "Dimension scores and scoring runs."},
        {"name": "Packs", "description": "Curated directive packs, build, and export."},
        {"name": "Similarity", "description": "Embedding-backed similarity search."},
        {"name": "Concepts", "description": "Cognitive analytics: compare, cluster, recommend, explain."},
        {"name": "Search", "description": "Full-text and vector search over directives."},
        {"name": "Verdict", "description": "Policy verdicts and evaluation triggers."},
        {"name": "Auth", "description": "Authentication and authorization (reserved for future use)."},
        {"name": "Health", "description": "Health, readiness, and liveness probes."},
        {"name": "root", "description": "Service root."},
    ],
    contact={"name": "DKB Runtime", "url": "https://github.com/songblaq/dkb-runtime"},
    license_info={"name": "MIT", "url": "https://opensource.org/licenses/MIT"},
)
register_dashboard_routes(app)
app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/", tags=["root"], response_model=RootResponse)
def root() -> RootResponse:
    return RootResponse(name=settings.app_name, status="ok")
