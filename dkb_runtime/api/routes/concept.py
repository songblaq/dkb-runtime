from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from dkb_runtime.api.deps import DbSession
from dkb_runtime.models import CanonicalDirective, DimensionModel
from dkb_runtime.services.cognitive_ops import (
    cluster_directives,
    compare_directives,
    explain_profile,
    get_directive_dimension_scores,
    recommend_similar,
)

router = APIRouter()


@router.get("/compare")
def compare_directives_route(
    db: DbSession,
    id1: Annotated[UUID, Query(description="First directive UUID")],
    id2: Annotated[UUID, Query(description="Second directive UUID")],
):
    """Compare two directives: score diff per dimension and embedding cosine distance (when available)."""
    try:
        return compare_directives(db, id1, id2)
    except ValueError as e:
        detail = str(e)
        if "not found" in detail.lower():
            raise HTTPException(status_code=404, detail=detail) from e
        raise HTTPException(status_code=400, detail=detail) from e


@router.get("/cluster")
def cluster_directives_route(
    db: DbSession,
    k: int = Query(default=5, ge=1, le=50, description="Number of clusters"),
):
    """K-means clustering on DKB score vectors for the active dimension model."""
    try:
        return cluster_directives(db, k=k)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/{directive_id}/recommend")
def recommend_similar_route(
    directive_id: UUID,
    db: DbSession,
    n: int = Query(default=5, ge=1, le=100),
    model: str | None = Query(default=None, description="Embedding model filter; latest if omitted"),
):
    """Recommend similar directives using embedding similarity."""
    try:
        return recommend_similar(db, directive_id, n=n, model_name=model)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/{directive_id}/explain")
def explain_directive_route(directive_id: UUID, db: DbSession):
    """Natural-language explanation of this directive's score profile (template-based, no LLM)."""
    if db.get(CanonicalDirective, directive_id) is None:
        raise HTTPException(status_code=404, detail="Directive not found")
    dim_model = db.scalars(select(DimensionModel).where(DimensionModel.is_active.is_(True))).first()
    if dim_model is None:
        raise HTTPException(status_code=400, detail="No active dimension model")
    smap = get_directive_dimension_scores(db, directive_id, dim_model.dimension_model_id)
    text_out = explain_profile(smap)
    return {
        "directive_id": str(directive_id),
        "dimension_model_id": str(dim_model.dimension_model_id),
        "explanation": text_out,
    }
