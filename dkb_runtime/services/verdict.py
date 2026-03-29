"""Verdict service — applies policy rules to generate verdicts."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session


@dataclass
class VerdictResult:
    verdict_id: UUID
    provenance_state: str
    trust_state: str
    legal_state: str
    lifecycle_state: str
    recommendation_state: str
    verdict_reason: str


def evaluate_directive(
    db: Session, directive_id: UUID
) -> VerdictResult:
    """Generate a verdict for a canonical directive.

    Verdict axes:
    - provenance: official / vendor / community / individual / unknown
    - trust: unknown / reviewing / verified / caution / blocked
    - legal: clear / custom / no_license / removed / restricted
    - lifecycle: active / stale / dormant / archived / disappeared
    - recommendation: candidate / preferred / merged / excluded / deprecated
    """
    raise NotImplementedError("verdict.evaluate_directive")
