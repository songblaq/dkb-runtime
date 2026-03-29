from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from dkb_runtime.api.deps import DbSession
from dkb_runtime.models import CanonicalDirective, Verdict
from dkb_runtime.schemas.verdict import VerdictRead
from dkb_runtime.services.verdict import evaluate_directive

router = APIRouter()


@router.get("/{directive_id}/verdict", response_model=VerdictRead)
def get_verdict(directive_id: UUID, db: DbSession):
    if db.get(CanonicalDirective, directive_id) is None:
        raise HTTPException(status_code=404, detail="Directive not found")
    v = db.scalars(
        select(Verdict).where(Verdict.directive_id == directive_id).order_by(Verdict.evaluated_at.desc()).limit(1)
    ).first()
    if v is None:
        raise HTTPException(status_code=404, detail="Verdict not found")
    return v


@router.post("/{directive_id}/evaluate", status_code=201, response_model=VerdictRead)
def trigger_evaluation(directive_id: UUID, db: DbSession):
    if db.get(CanonicalDirective, directive_id) is None:
        raise HTTPException(status_code=404, detail="Directive not found")
    try:
        evaluate_directive(db, directive_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    db.commit()
    v = db.scalars(
        select(Verdict).where(Verdict.directive_id == directive_id).order_by(Verdict.evaluated_at.desc()).limit(1)
    ).first()
    if v is None:
        raise HTTPException(status_code=500, detail="Verdict not persisted")
    return v
