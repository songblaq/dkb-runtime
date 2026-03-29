from __future__ import annotations

from fastapi import APIRouter, Query
from sqlalchemy import select, text

from dkb_runtime.api.deps import DbSession
from dkb_runtime.models import CanonicalDirective, DirectiveEmbedding
from dkb_runtime.schemas.directive import FTSSearchItem, VectorSearchItem, VectorSearchRequest

router = APIRouter()


@router.get("/raw", response_model=list[FTSSearchItem])
def search_raw(
    db: DbSession,
    q: str = Query(min_length=1),
    limit: int = Query(default=10, le=50),
):
    sql = text(
        """
        SELECT
          raw_directive_id AS id,
          raw_name AS name,
          summary_raw AS summary,
          ts_rank_cd(tsv, websearch_to_tsquery('simple', :q)) AS rank
        FROM dkb.raw_directive
        WHERE tsv @@ websearch_to_tsquery('simple', :q)
        ORDER BY rank DESC, raw_name ASC
        LIMIT :limit
        """
    )
    rows = db.execute(sql, {"q": q, "limit": limit}).mappings().all()
    return [FTSSearchItem(**row) for row in rows]


@router.get("/directives", response_model=list[FTSSearchItem])
def search_directives(
    db: DbSession,
    q: str = Query(min_length=1),
    limit: int = Query(default=10, le=50),
):
    sql = text(
        """
        SELECT
          directive_id AS id,
          preferred_name AS name,
          normalized_summary AS summary,
          ts_rank_cd(tsv, websearch_to_tsquery('simple', :q)) AS rank
        FROM dkb.canonical_directive
        WHERE tsv @@ websearch_to_tsquery('simple', :q)
        ORDER BY rank DESC, preferred_name ASC
        LIMIT :limit
        """
    )
    rows = db.execute(sql, {"q": q, "limit": limit}).mappings().all()
    return [FTSSearchItem(**row) for row in rows]


@router.post("/vector", response_model=list[VectorSearchItem])
def vector_search(db: DbSession, payload: VectorSearchRequest):
    stmt = (
        select(
            CanonicalDirective.directive_id,
            CanonicalDirective.preferred_name,
            CanonicalDirective.normalized_summary,
            DirectiveEmbedding.embedding_model,
            DirectiveEmbedding.embedding.cosine_distance(payload.embedding).label("distance"),
        )
        .join(DirectiveEmbedding, DirectiveEmbedding.directive_id == CanonicalDirective.directive_id)
        .order_by(text("distance ASC"))
        .limit(payload.limit)
    )

    if payload.embedding_model:
        stmt = stmt.where(DirectiveEmbedding.embedding_model == payload.embedding_model)

    rows = db.execute(stmt).all()
    return [
        VectorSearchItem(
            directive_id=row.directive_id,
            preferred_name=row.preferred_name,
            normalized_summary=row.normalized_summary,
            embedding_model=row.embedding_model,
            distance=float(row.distance),
        )
        for row in rows
    ]
