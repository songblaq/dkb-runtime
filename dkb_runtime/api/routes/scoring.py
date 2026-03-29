from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from dkb_runtime.api.deps import DbSession
from dkb_runtime.models import CanonicalDirective, DimensionModel, DimensionScore
from dkb_runtime.schemas.scoring import DimensionScoreRead
from dkb_runtime.services.scoring import score_directive

router = APIRouter()


@router.get("/{directive_id}/scores", response_model=list[DimensionScoreRead])
def get_scores(directive_id: UUID, db: DbSession):
    if db.get(CanonicalDirective, directive_id) is None:
        raise HTTPException(status_code=404, detail="Directive not found")
    stmt = (
        select(DimensionScore)
        .where(DimensionScore.directive_id == directive_id)
        .order_by(
            DimensionScore.scored_at.desc(),
            DimensionScore.dimension_group,
            DimensionScore.dimension_key,
        )
    )
    return db.scalars(stmt).all()


@router.post("/{directive_id}/score", status_code=201, response_model=list[DimensionScoreRead])
def trigger_scoring(
    directive_id: UUID,
    db: DbSession,
    model_id: Annotated[UUID | None, Query()] = None,
):
    if db.get(CanonicalDirective, directive_id) is None:
        raise HTTPException(status_code=404, detail="Directive not found")
    if model_id is None:
        model = db.scalars(select(DimensionModel).order_by(DimensionModel.created_at.desc()).limit(1)).first()
        if model is None:
            raise HTTPException(status_code=400, detail="No dimension model registered")
        model_id = model.dimension_model_id
    else:
        if db.get(DimensionModel, model_id) is None:
            raise HTTPException(status_code=404, detail="Dimension model not found")
    score_directive(db, directive_id, model_id)
    db.commit()
    stmt = (
        select(DimensionScore)
        .where(
            DimensionScore.directive_id == directive_id,
            DimensionScore.dimension_model_id == model_id,
        )
        .order_by(DimensionScore.dimension_group, DimensionScore.dimension_key)
    )
    return db.scalars(stmt).all()
