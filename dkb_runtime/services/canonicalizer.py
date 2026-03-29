"""Canonicalizer service — deduplicates and normalizes directives."""

from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, selectinload

from dkb_runtime.models import (
    CanonicalDirective,
    DirectiveRelation,
    RawDirective,
    RawToCanonicalMap,
)
from dkb_runtime.services.audit import log_audit


@dataclass
class CanonicalResult:
    directive_id: UUID
    preferred_name: str
    mapped_raw_count: int


def _normalize_name(raw_name: str) -> str:
    name = raw_name.lower().strip()
    for prefix in ["oh-my-", "awesome-", "claude-code-", "agent-", "skill-"]:
        if name.startswith(prefix):
            name = name[len(prefix) :]
    name = re.sub(r"[-\s]+", "_", name)
    name = re.sub(r"[^a-z0-9_]", "", name)
    return name


def _pick_best_raw(raws: list[RawDirective]) -> RawDirective:
    def key(r: RawDirective) -> tuple[int, int]:
        n_ev = len(r.evidence_items) if r.evidence_items else 0
        return (n_ev, len(r.summary_raw or ""))

    return max(raws, key=key)


def _relation_exists(
    db: Session,
    left_id: UUID,
    right_id: UUID,
    relation_type: str,
) -> bool:
    stmt = select(DirectiveRelation).where(
        DirectiveRelation.relation_type == relation_type,
        or_(
            and_(
                DirectiveRelation.left_directive_id == left_id,
                DirectiveRelation.right_directive_id == right_id,
            ),
            and_(
                DirectiveRelation.left_directive_id == right_id,
                DirectiveRelation.right_directive_id == left_id,
            ),
        ),
    )
    return db.scalars(stmt.limit(1)).first() is not None


def canonicalize(db: Session, raw_directive_ids: list[UUID]) -> list[CanonicalResult]:
    if not raw_directive_ids:
        return []

    raws = db.scalars(
        select(RawDirective)
        .options(selectinload(RawDirective.evidence_items))
        .where(RawDirective.raw_directive_id.in_(raw_directive_ids))
    ).all()
    if len(raws) != len(set(raw_directive_ids)):
        raise ValueError("One or more raw_directive_ids were not found")

    existing_canons = db.scalars(select(CanonicalDirective)).all()
    norm_to_canon: dict[str, CanonicalDirective] = {}
    for c in existing_canons:
        n = _normalize_name(c.preferred_name)
        if n not in norm_to_canon:
            norm_to_canon[n] = c

    groups: dict[str, list[RawDirective]] = {}
    for r in raws:
        groups.setdefault(_normalize_name(r.raw_name), []).append(r)

    results: list[CanonicalResult] = []
    touched_directives: dict[UUID, list[RawDirective]] = {}

    for norm, group in groups.items():
        best = _pick_best_raw(group)
        existing = norm_to_canon.get(norm)
        if existing:
            canon = existing
        else:
            canon = CanonicalDirective(
                preferred_name=best.raw_name,
                normalized_summary=best.summary_raw,
                primary_human_label=best.raw_name,
                scope="global",
                status="active",
                canonical_meta={"normalized_key": norm},
            )
            db.add(canon)
            db.flush()
            norm_to_canon[norm] = canon

        touched_directives.setdefault(canon.directive_id, []).extend(group)

        for r in group:
            db.add(
                RawToCanonicalMap(
                    raw_directive_id=r.raw_directive_id,
                    directive_id=canon.directive_id,
                    mapping_score=1.0 if r.raw_directive_id == best.raw_directive_id else 0.85,
                    mapping_reason="primary" if len(group) == 1 else "dedup",
                    mapping_status="accepted",
                )
            )

    uniq_canons = {c.directive_id: c for c in norm_to_canon.values()}.values()
    canon_list = list(uniq_canons)

    for i, a in enumerate(canon_list):
        for b in canon_list[i + 1 :]:
            na = _normalize_name(a.preferred_name)
            nb = _normalize_name(b.preferred_name)
            if na == nb:
                continue
            if len(na) < 3 or len(nb) < 3:
                continue
            if not (na in nb or nb in na):
                continue
            left, right = (a, b) if len(na) <= len(nb) else (b, a)
            if left.directive_id == right.directive_id:
                continue
            if _relation_exists(db, left.directive_id, right.directive_id, "variant_of"):
                continue
            db.add(
                DirectiveRelation(
                    left_directive_id=left.directive_id,
                    right_directive_id=right.directive_id,
                    relation_type="variant_of",
                    strength=0.4,
                    explanation="normalized name substring",
                )
            )

    for directive_id, mapped_raws in touched_directives.items():
        canon = db.get(CanonicalDirective, directive_id)
        if canon:
            results.append(
                CanonicalResult(
                    directive_id=directive_id,
                    preferred_name=canon.preferred_name,
                    mapped_raw_count=len(mapped_raws),
                )
            )

    log_audit(
        db,
        "directive",
        results[0].directive_id if results else raws[0].raw_directive_id,
        "canonicalized",
        {"raw_count": len(raws), "canonical_count": len(results)},
    )
    db.flush()

    return results
