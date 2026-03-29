from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from dkb_runtime.api.deps import DbSession
from dkb_runtime.models import RawDirective, Source, SourceSnapshot
from dkb_runtime.schemas.source import (
    RawDirectiveCreate,
    RawDirectiveRead,
    SnapshotCreate,
    SnapshotRead,
    SourceCreate,
    SourceRead,
)

router = APIRouter()


@router.get("", response_model=list[SourceRead])
def list_sources(db: DbSession, limit: int = Query(default=50, le=200), offset: int = 0):
    stmt = select(Source).order_by(Source.last_seen_at.desc()).limit(limit).offset(offset)
    return db.scalars(stmt).all()


@router.post("", response_model=SourceRead, status_code=201)
def create_source(payload: SourceCreate, db: DbSession):
    source = Source(
        source_kind=payload.source_kind,
        origin_uri=payload.origin_uri,
        owner_name=payload.owner_name,
        canonical_source_name=payload.canonical_source_name,
        provenance_hint=payload.provenance_hint,
        metadata_json=payload.metadata,
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


@router.get("/{source_id}", response_model=SourceRead)
def get_source(source_id: UUID, db: DbSession):
    source = db.get(Source, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return source


@router.get("/{source_id}/snapshots", response_model=list[SnapshotRead])
def list_snapshots(
    source_id: UUID, db: DbSession, limit: int = Query(default=50, le=200), offset: int = 0
):
    stmt = (
        select(SourceSnapshot)
        .where(SourceSnapshot.source_id == source_id)
        .order_by(SourceSnapshot.captured_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return db.scalars(stmt).all()


@router.post("/{source_id}/snapshots", response_model=SnapshotRead, status_code=201)
def create_snapshot(source_id: UUID, payload: SnapshotCreate, db: DbSession):
    source = db.get(Source, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    snapshot = SourceSnapshot(
        source_id=source.source_id,
        revision_ref=payload.revision_ref,
        revision_type=payload.revision_type,
        checksum=payload.checksum,
        license_text=payload.license_text,
        raw_blob_uri=payload.raw_blob_uri,
        capture_status=payload.capture_status,
        snapshot_meta=payload.snapshot_meta,
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return snapshot


@router.get("/snapshots/{snapshot_id}/raw-directives", response_model=list[RawDirectiveRead])
def list_raw_directives(
    snapshot_id: UUID, db: DbSession, limit: int = Query(default=50, le=200), offset: int = 0
):
    stmt = (
        select(RawDirective)
        .where(RawDirective.snapshot_id == snapshot_id)
        .order_by(RawDirective.raw_name.asc())
        .limit(limit)
        .offset(offset)
    )
    return db.scalars(stmt).all()


@router.post(
    "/snapshots/{snapshot_id}/raw-directives", response_model=RawDirectiveRead, status_code=201
)
def create_raw_directive(snapshot_id: UUID, payload: RawDirectiveCreate, db: DbSession):
    snapshot = db.get(SourceSnapshot, snapshot_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found")

    item = RawDirective(
        snapshot_id=snapshot.snapshot_id,
        raw_name=payload.raw_name,
        entry_path=payload.entry_path,
        declared_type=payload.declared_type,
        content_format=payload.content_format,
        language_code=payload.language_code,
        summary_raw=payload.summary_raw,
        body_raw=payload.body_raw,
        metadata_json=payload.metadata,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item
