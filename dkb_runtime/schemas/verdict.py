from __future__ import annotations

from datetime import datetime
from uuid import UUID

from dkb_runtime.schemas.common import ORMModel


class VerdictRead(ORMModel):
    verdict_id: UUID
    directive_id: UUID
    dimension_model_id: UUID
    provenance_state: str
    trust_state: str
    legal_state: str
    lifecycle_state: str
    recommendation_state: str
    verdict_reason: str | None = None
    policy_trace: dict
    evaluated_at: datetime
