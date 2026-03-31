from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select

from dkb_runtime.api.deps import DbSession
from dkb_runtime.api.middleware.auth import get_current_user
from dkb_runtime.models import CanonicalDirective
from dkb_runtime.schemas.directive import CanonicalDirectiveCreate, CanonicalDirectiveRead

router = APIRouter()


@router.get("", response_model=list[CanonicalDirectiveRead])
def list_directives(
    db: DbSession,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    status: str | None = None,
):
    stmt = select(CanonicalDirective).order_by(CanonicalDirective.preferred_name.asc()).limit(limit).offset(offset)
    if status:
        stmt = stmt.where(CanonicalDirective.status == status)
    return db.scalars(stmt).all()


@router.post("", response_model=CanonicalDirectiveRead, status_code=201, dependencies=[Depends(get_current_user)])
def create_directive(payload: CanonicalDirectiveCreate, db: DbSession):
    directive = CanonicalDirective(
        preferred_name=payload.preferred_name,
        normalized_summary=payload.normalized_summary,
        primary_human_label=payload.primary_human_label,
        scope=payload.scope,
        status=payload.status,
        canonical_meta=payload.canonical_meta,
    )
    db.add(directive)
    db.commit()
    db.refresh(directive)
    return directive


@router.get("/{directive_id}", response_model=CanonicalDirectiveRead)
def get_directive(directive_id: UUID, db: DbSession):
    directive = db.get(CanonicalDirective, directive_id)
    if not directive:
        raise HTTPException(status_code=404, detail="Directive not found")
    return directive
