"""Scoring service — computes DG dimension scores."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class DimensionScoreResult:
    dimension_key: str
    score: float
    confidence: float
    explanation: str


async def score_directive(
    db: AsyncSession, directive_id: UUID, model_id: UUID
) -> list[DimensionScoreResult]:
    """Score a canonical directive across all dimensions.

    Dimension groups:
    - Form: skillness, agentness, workflowness, commandness, pluginness
    - Function: planning, review, coding, research, ops, writing, content, orchestration
    - Execution: atomicity, autonomy, multi_stepness, tool_dependence, composability, reusability
    - Governance: officialness, legal_clarity, maintenance_health, install_verifiability, trustworthiness
    - Adoption: star_signal, fork_signal, mention_signal, install_signal, freshness
    - Clarity: naming_clarity, description_clarity, io_clarity, example_coverage, overlap_ambiguity_inverse
    """
    raise NotImplementedError("scoring.score_directive")
