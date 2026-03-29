"""Exporter service — exports curated packs to various formats."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from dkb_runtime.models import DimensionScore, Pack, PackItem
from dkb_runtime.services.audit import log_audit


@dataclass
class ExportResult:
    format: str
    output_path: Path
    file_count: int


def _sanitize_filename(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_-]+", "_", name.lower()).strip("_")
    return s or "directive"


def _form_scores(db: Session, directive_id: UUID, model_id: UUID | None) -> tuple[float, float]:
    if model_id is None:
        return 0.0, 0.0
    rows = db.scalars(
        select(DimensionScore)
        .where(
            DimensionScore.directive_id == directive_id,
            DimensionScore.dimension_model_id == model_id,
            DimensionScore.dimension_group == "form",
        )
        .order_by(DimensionScore.scored_at.desc())
    ).all()
    best: dict[str, float] = {}
    for r in rows:
        if r.dimension_key not in best:
            best[r.dimension_key] = r.score
    return float(best.get("skillness", 0.0)), float(best.get("agentness", 0.0))


def _load_pack(db: Session, pack_id: UUID) -> Pack:
    p = db.scalars(
        select(Pack)
        .where(Pack.pack_id == pack_id)
        .options(
            selectinload(Pack.items).selectinload(PackItem.directive),
        )
    ).one_or_none()
    if not p:
        raise ValueError(f"Pack not found: {pack_id}")
    return p


def _latest_model_for_directive(db: Session, directive_id: UUID) -> UUID | None:
    return db.scalars(
        select(DimensionScore.dimension_model_id)
        .where(DimensionScore.directive_id == directive_id)
        .order_by(DimensionScore.scored_at.desc())
        .limit(1)
    ).first()


def export_claude_code(db: Session, pack_id: UUID, output_dir: Path) -> ExportResult:
    pack = _load_pack(db, pack_id)
    output_dir.mkdir(parents=True, exist_ok=True)
    agents_dir = output_dir / "agents"
    skills_dir = output_dir / "skills"
    agents_dir.mkdir(exist_ok=True)
    skills_dir.mkdir(exist_ok=True)

    count = 0
    settings_items: list[dict] = []

    for item in pack.items:
        d = item.directive
        if d is None:
            continue
        mid = _latest_model_for_directive(db, d.directive_id)
        skillness, agentness = _form_scores(db, d.directive_id, mid)
        name = _sanitize_filename(d.preferred_name)
        body = f"# {d.preferred_name}\n\n{d.normalized_summary or ''}\n"
        if agentness >= skillness:
            path = agents_dir / f"{name}.md"
        else:
            path = skills_dir / f"{name}.md"
        path.write_text(body, encoding="utf-8")
        count += 1
        settings_items.append(
            {
                "directive_id": str(d.directive_id),
                "path": str(path.relative_to(output_dir)),
                "priority": item.priority_weight,
            }
        )

    settings_path = output_dir / "settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "pack_key": pack.pack_key,
                "pack_name": pack.pack_name,
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "items": settings_items,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    count += 1

    log_audit(
        db,
        "pack",
        pack_id,
        "exported",
        {"format": "claude-code", "file_count": count},
    )
    db.flush()

    return ExportResult(format="claude-code", output_path=output_dir, file_count=count)


def export_skill_md(db: Session, pack_id: UUID, output_dir: Path) -> ExportResult:
    pack = _load_pack(db, pack_id)
    output_dir.mkdir(parents=True, exist_ok=True)
    count = 0

    for item in pack.items:
        d = item.directive
        if d is None:
            continue
        name = _sanitize_filename(d.preferred_name)
        skill_dir = output_dir / name
        skill_dir.mkdir(parents=True, exist_ok=True)
        md = skill_dir / "SKILL.md"
        content = (
            "---\n"
            f"name: {d.preferred_name}\n"
            f"directive_id: {d.directive_id}\n"
            "---\n\n"
            f"# {d.preferred_name}\n\n"
            f"{d.normalized_summary or ''}\n"
        )
        md.write_text(content, encoding="utf-8")
        count += 1

    log_audit(
        db,
        "pack",
        pack_id,
        "exported",
        {"format": "skill-md", "file_count": count},
    )
    db.flush()

    return ExportResult(format="skill-md", output_path=output_dir, file_count=count)


def export_snapshot(db: Session, pack_id: UUID, output_dir: Path) -> ExportResult:
    pack = _load_pack(db, pack_id)
    output_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "version": "0.1.0",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "pack": {
            "pack_id": str(pack.pack_id),
            "pack_key": pack.pack_key,
            "pack_name": pack.pack_name,
            "pack_goal": pack.pack_goal,
            "pack_type": pack.pack_type,
            "status": pack.status,
            "selection_policy": pack.selection_policy,
        },
        "items": [],
    }

    for item in pack.items:
        d = item.directive
        if d is None:
            continue
        mid = _latest_model_for_directive(db, d.directive_id)
        scores: dict[str, float] = {}
        if mid:
            rows = db.scalars(
                select(DimensionScore)
                .where(
                    DimensionScore.directive_id == d.directive_id,
                    DimensionScore.dimension_model_id == mid,
                )
                .order_by(DimensionScore.scored_at.desc())
            ).all()
            for r in rows:
                if r.dimension_key not in scores:
                    scores[r.dimension_key] = r.score
        payload["items"].append(
            {
                "directive_id": str(d.directive_id),
                "preferred_name": d.preferred_name,
                "summary": d.normalized_summary,
                "inclusion_reason": item.inclusion_reason,
                "priority_weight": item.priority_weight,
                "scores": scores,
            }
        )

    out = output_dir / f"pack_{pack.pack_key}_snapshot.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    log_audit(
        db,
        "pack",
        pack_id,
        "exported",
        {"format": "snapshot", "file_count": 1},
    )
    db.flush()

    return ExportResult(format="snapshot", output_path=out, file_count=1)
