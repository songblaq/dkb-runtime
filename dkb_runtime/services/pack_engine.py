"""Pack engine — builds curated packs from scored/verdicted directives."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from dkb_runtime.models import (
    CanonicalDirective,
    DimensionScore,
    Pack,
    PackItem,
    Verdict,
)
from dkb_runtime.services.audit import log_audit


@dataclass
class PackBuildResult:
    pack_id: UUID
    pack_name: str
    item_count: int
    status: str


def _latest_verdict(db: Session, directive_id: UUID) -> Verdict | None:
    return db.scalars(
        select(Verdict)
        .where(Verdict.directive_id == directive_id)
        .order_by(Verdict.evaluated_at.desc())
        .limit(1)
    ).first()


def _scores_map_latest(db: Session, directive_id: UUID, model_id: UUID) -> dict[str, float]:
    rows = db.scalars(
        select(DimensionScore)
        .where(
            DimensionScore.directive_id == directive_id,
            DimensionScore.dimension_model_id == model_id,
        )
        .order_by(DimensionScore.scored_at.desc())
    ).all()
    out: dict[str, float] = {}
    for r in rows:
        if r.dimension_key not in out:
            out[r.dimension_key] = r.score
    return out


def _utility_score(scores: dict[str, float]) -> float:
    keys = [
        "skillness",
        "agentness",
        "trustworthiness",
        "description_clarity",
        "reusability",
    ]
    vals = [scores.get(k, 0.0) for k in keys]
    return sum(vals) / max(len(keys), 1)


def build_pack(db: Session, pack_id: UUID) -> PackBuildResult:
    pack = db.get(Pack, pack_id)
    if not pack:
        raise ValueError(f"Pack not found: {pack_id}")

    policy = pack.selection_policy or {}
    min_scores: dict[str, float] = policy.get("min_scores") or {}
    trust_allow = policy.get("trust_states")
    legal_allow = policy.get("legal_states")
    exclude_rec = set(policy.get("exclude_recommendations") or ["excluded", "deprecated"])

    directives = db.scalars(select(CanonicalDirective)).all()
    candidates: list[tuple[CanonicalDirective, float]] = []

    for d in directives:
        v = _latest_verdict(db, d.directive_id)
        if v is None:
            continue
        if trust_allow is not None and v.trust_state not in trust_allow:
            continue
        if legal_allow is not None and v.legal_state not in legal_allow:
            continue
        if v.recommendation_state in exclude_rec:
            continue

        scores = _scores_map_latest(db, d.directive_id, v.dimension_model_id)
        ok = True
        for compound_key, minimum in min_scores.items():
            if "." in compound_key:
                _, dim_key = compound_key.split(".", 1)
            else:
                dim_key = compound_key
            if scores.get(dim_key, 0.0) < float(minimum):
                ok = False
                break
        if not ok:
            continue

        u = _utility_score(scores)
        candidates.append((d, u))

    candidates.sort(key=lambda x: x[1], reverse=True)

    db.execute(delete(PackItem).where(PackItem.pack_id == pack_id))

    max_items = int(policy.get("max_items", 100))
    chosen = candidates[:max_items]
    n = len(chosen)
    for rank, (d, u) in enumerate(chosen):
        if n <= 1:
            pw = 1.0
        else:
            pw = 1.0 - (rank / (n - 1)) * 0.5
        db.add(
            PackItem(
                pack_id=pack_id,
                directive_id=d.directive_id,
                inclusion_reason="selection_policy",
                priority_weight=min(1.0, max(0.0, pw)),
                role_fit={"utility": u},
            )
        )

    pack.status = "active"
    db.flush()

    log_audit(
        db,
        "pack",
        pack_id,
        "packed",
        {"item_count": len(chosen)},
    )
    db.flush()

    return PackBuildResult(
        pack_id=pack_id,
        pack_name=pack.pack_name,
        item_count=len(chosen),
        status=pack.status,
    )
