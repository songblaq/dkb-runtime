from __future__ import annotations

import uuid
from uuid import UUID

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from dkb_runtime.api.deps import DbSession
from dkb_runtime.core.paths import repo_root
from dkb_runtime.models import Pack
from dkb_runtime.schemas.pack import PackCreate, PackRead
from dkb_runtime.services.exporter import export_claude_code, export_skill_md, export_snapshot
from dkb_runtime.services.pack_engine import build_pack

router = APIRouter()


@router.get("", response_model=list[PackRead])
def list_packs(db: DbSession):
    return db.scalars(select(Pack).order_by(Pack.created_at.desc())).all()


@router.post("", response_model=PackRead, status_code=201)
def create_pack(payload: PackCreate, db: DbSession):
    existing = db.scalars(select(Pack).where(Pack.pack_key == payload.pack_key).limit(1)).first()
    if existing:
        raise HTTPException(status_code=409, detail="pack_key already exists")
    pack = Pack(
        pack_key=payload.pack_key,
        pack_name=payload.pack_name,
        pack_goal=payload.pack_goal,
        pack_type=payload.pack_type,
        selection_policy=payload.selection_policy,
        status="draft",
    )
    db.add(pack)
    db.commit()
    db.refresh(pack)
    return pack


@router.get("/{pack_id}", response_model=PackRead)
def get_pack(pack_id: UUID, db: DbSession):
    pack = db.get(Pack, pack_id)
    if not pack:
        raise HTTPException(status_code=404, detail="Pack not found")
    return pack


@router.delete("/{pack_id}", status_code=204)
def delete_pack(pack_id: UUID, db: DbSession):
    pack = db.get(Pack, pack_id)
    if not pack:
        raise HTTPException(status_code=404, detail="Pack not found")
    db.delete(pack)
    db.commit()


@router.post("/{pack_id}/build", status_code=200)
def trigger_build(pack_id: UUID, db: DbSession):
    if db.get(Pack, pack_id) is None:
        raise HTTPException(status_code=404, detail="Pack not found")
    result = build_pack(db, pack_id)
    db.commit()
    return {
        "pack_id": str(result.pack_id),
        "pack_name": result.pack_name,
        "item_count": result.item_count,
        "status": result.status,
    }


@router.post("/{pack_id}/export/{export_format}")
def trigger_export(pack_id: UUID, export_format: str, db: DbSession):
    if db.get(Pack, pack_id) is None:
        raise HTTPException(status_code=404, detail="Pack not found")
    base = repo_root() / "storage" / "exports" / str(pack_id) / str(uuid.uuid4())
    base.mkdir(parents=True, exist_ok=True)
    fmt = export_format.lower().replace("_", "-")
    if fmt in ("claude-code", "claude_code"):
        result = export_claude_code(db, pack_id, base)
    elif fmt in ("skill-md", "skill_md"):
        result = export_skill_md(db, pack_id, base)
    elif fmt == "snapshot":
        result = export_snapshot(db, pack_id, base)
    else:
        raise HTTPException(
            status_code=400,
            detail="Invalid format; use claude-code, skill-md, or snapshot",
        )
    db.commit()
    return {
        "format": result.format,
        "output_path": str(result.output_path),
        "file_count": result.file_count,
    }
