"""Verdict service — applies policy rules to generate verdicts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from dkb_runtime.core.paths import repo_root
from dkb_runtime.models import (
    CanonicalDirective,
    DimensionScore,
    RawDirective,
    RawToCanonicalMap,
    SourceSnapshot,
    Verdict,
)
from dkb_runtime.services.audit import log_audit

_POLICY_PATH = repo_root() / "config" / "verdict_policy_v0_1.json"


@dataclass
class VerdictResult:
    verdict_id: UUID
    provenance_state: str
    trust_state: str
    legal_state: str
    lifecycle_state: str
    recommendation_state: str
    verdict_reason: str


def _load_policy() -> dict:
    return json.loads(_POLICY_PATH.read_text(encoding="utf-8"))


def _latest_model_id_for_directive(db: Session, directive_id: UUID) -> UUID:
    model_id = db.scalars(
        select(DimensionScore.dimension_model_id)
        .where(DimensionScore.directive_id == directive_id)
        .order_by(DimensionScore.scored_at.desc())
        .limit(1)
    ).first()
    if model_id is None:
        raise ValueError(f"No dimension scores for directive {directive_id}; run scoring first")
    return model_id


def _scores_by_key(db: Session, directive_id: UUID, model_id: UUID) -> dict[str, float]:
    rows = db.scalars(
        select(DimensionScore)
        .where(
            DimensionScore.directive_id == directive_id,
            DimensionScore.dimension_model_id == model_id,
        )
        .order_by(DimensionScore.scored_at.desc())
    ).all()
    best: dict[str, DimensionScore] = {}
    for r in rows:
        if r.dimension_key not in best:
            best[r.dimension_key] = r
    return {k: v.score for k, v in best.items()}


def _snapshot_license_and_source(db: Session, directive_id: UUID) -> tuple[str | None, str | None]:
    d = db.scalars(
        select(CanonicalDirective)
        .where(CanonicalDirective.directive_id == directive_id)
        .options(
            selectinload(CanonicalDirective.mappings)
            .selectinload(RawToCanonicalMap.raw_directive)
            .selectinload(RawDirective.snapshot)
            .selectinload(SourceSnapshot.source),
        )
    ).one_or_none()
    if not d or not d.mappings:
        return None, None
    rd = d.mappings[0].raw_directive
    if rd is None or rd.snapshot is None:
        return None, None
    snap = rd.snapshot
    lic = snap.license_text
    prov = snap.source.provenance_hint if snap.source else None
    return lic, prov


def _match_rule_condition(states: dict[str, str], cond: dict) -> bool:
    for axis, expected in cond.items():
        actual = states.get(axis)
        if isinstance(expected, list):
            if actual not in expected:
                return False
        elif actual != expected:
            return False
    return True


def _apply_rules(
    policy: dict,
    states: dict[str, str],
) -> tuple[dict[str, str], list[str]]:
    trace: list[str] = []
    out = dict(states)
    for rule in policy.get("example_rules", []):
        cond = rule.get("if") or {}
        if _match_rule_condition(out, cond):
            then = rule.get("then") or {}
            for k, v in then.items():
                out[k] = v
            trace.append(rule.get("name", "rule"))
    return out, trace


def evaluate_directive(db: Session, directive_id: UUID) -> VerdictResult:
    directive = db.get(CanonicalDirective, directive_id)
    if not directive:
        raise ValueError(f"Directive not found: {directive_id}")

    policy = _load_policy()
    defaults = policy.get("defaults", {})
    model_id = _latest_model_id_for_directive(db, directive_id)
    scores = _scores_by_key(db, directive_id, model_id)
    license_text, provenance_hint = _snapshot_license_and_source(db, directive_id)

    states = {
        "provenance_state": defaults.get("provenance_state", "unknown"),
        "trust_state": defaults.get("trust_state", "unknown"),
        "legal_state": defaults.get("legal_state", "custom"),
        "lifecycle_state": defaults.get("lifecycle_state", "active"),
        "recommendation_state": defaults.get("recommendation_state", "candidate"),
    }

    off = scores.get("officialness", 0.0)
    if provenance_hint:
        hint = provenance_hint.lower()
        if hint in ("official", "vendor", "community", "individual"):
            states["provenance_state"] = hint
    if off >= 0.65 and states["provenance_state"] == "unknown":
        states["provenance_state"] = "vendor"

    if scores:
        states["trust_state"] = "reviewing"

    if license_text and len(license_text.strip()) > 20:
        lt = license_text.lower()
        if "mit" in lt or "apache" in lt or "bsd" in lt:
            states["legal_state"] = "clear"
        else:
            states["legal_state"] = "custom"
    else:
        states["legal_state"] = "no_license"

    fresh = scores.get("freshness", 0.5)
    if fresh < 0.1:
        states["lifecycle_state"] = "dormant"
    elif fresh < 0.25:
        states["lifecycle_state"] = "stale"

    if directive.status == "archived":
        states["lifecycle_state"] = "archived"

    states, trace = _apply_rules(policy, states)

    reason_parts = [
        f"provenance={states['provenance_state']}",
        f"trust={states['trust_state']}",
        f"legal={states['legal_state']}",
        f"lifecycle={states['lifecycle_state']}",
        f"recommendation={states['recommendation_state']}",
    ]
    if trace:
        reason_parts.append("rules=" + ",".join(trace))

    verdict = Verdict(
        directive_id=directive_id,
        dimension_model_id=model_id,
        provenance_state=states["provenance_state"],
        trust_state=states["trust_state"],
        legal_state=states["legal_state"],
        lifecycle_state=states["lifecycle_state"],
        recommendation_state=states["recommendation_state"],
        verdict_reason="; ".join(reason_parts),
        policy_trace={"applied_rules": trace, "defaults": defaults},
    )
    db.add(verdict)
    db.flush()

    log_audit(
        db,
        "directive",
        directive_id,
        "verdicted",
        {"verdict_id": str(verdict.verdict_id)},
    )
    db.flush()

    return VerdictResult(
        verdict_id=verdict.verdict_id,
        provenance_state=verdict.provenance_state,
        trust_state=verdict.trust_state,
        legal_state=verdict.legal_state,
        lifecycle_state=verdict.lifecycle_state,
        recommendation_state=verdict.recommendation_state,
        verdict_reason=verdict.verdict_reason or "",
    )
