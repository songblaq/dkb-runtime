from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import select

from dkb_runtime.api.deps import DbSession
from dkb_runtime.api.middleware.rate_limit import limiter
from dkb_runtime.models import CanonicalDirective
from dkb_runtime.schemas.directive import SimilarityResultItem
from dkb_runtime.services.embedding import (
    find_similar,
    find_similar_to_directive,
    generate_embedding,
)

router = APIRouter()


def _enrich_similarity(
    db,
    pairs: list[tuple[UUID, float]],
) -> list[SimilarityResultItem]:
    if not pairs:
        return []
    ids = [p[0] for p in pairs]
    dist = dict(pairs)
    directives = db.scalars(select(CanonicalDirective).where(CanonicalDirective.directive_id.in_(ids))).all()
    by_id = {d.directive_id: d for d in directives}
    return [
        SimilarityResultItem(
            directive_id=did,
            preferred_name=by_id[did].preferred_name,
            normalized_summary=by_id[did].normalized_summary,
            distance=dist[did],
        )
        for did, _ in pairs
        if did in by_id
    ]


@router.get("/similar", response_model=list[SimilarityResultItem])
@limiter.limit("10/minute")
def similar_by_text(
    request: Request,
    db: DbSession,
    q: str = Query(min_length=1, description="Query text to embed and match"),
    limit: int = Query(default=10, ge=1, le=100),
    model: str = Query(default="text-embedding-3-small", description="Embedding model name (stored rows)"),
):
    """Text-based similarity: embed ``q`` then rank directives by cosine distance."""
    vec = generate_embedding(q, model=model)
    pairs = find_similar(db, vec, limit=limit, model_name=model)
    return _enrich_similarity(db, pairs)


@router.get("/{directive_id}/similar", response_model=list[SimilarityResultItem])
def similar_to_directive(
    directive_id: UUID,
    db: DbSession,
    limit: int = Query(default=10, ge=1, le=100),
    model: str | None = Query(default=None, description="Filter by stored embedding model; latest if omitted"),
):
    """Rank other directives by distance to this directive's stored embedding."""
    if db.get(CanonicalDirective, directive_id) is None:
        raise HTTPException(status_code=404, detail="Directive not found")
    pairs = find_similar_to_directive(db, directive_id, limit=limit, model_name=model)
    return _enrich_similarity(db, pairs)
