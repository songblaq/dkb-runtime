from __future__ import annotations

from datetime import datetime
from uuid import UUID

from dkb_runtime.schemas.common import ORMModel


class DimensionScoreRead(ORMModel):
    dimension_score_id: UUID
    directive_id: UUID
    dimension_model_id: UUID
    dimension_group: str
    dimension_key: str
    score: float
    confidence: float
    explanation: str | None = None
    features: dict
    scored_at: datetime
