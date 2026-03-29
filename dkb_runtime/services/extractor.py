"""Extractor service — parses snapshots into raw directives."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class RawDirectiveResult:
    raw_directive_id: UUID
    raw_name: str
    declared_type: str
    evidence_count: int


async def extract_directives(
    db: AsyncSession, snapshot_id: UUID
) -> list[RawDirectiveResult]:
    """Walk a snapshot's filesystem and extract raw directives + evidence.

    Detection priority:
    1. SKILL.md files
    2. agents/*.md, AGENTS.md
    3. *.prompt.md, prompts/*.md
    4. workflows/*.md
    5. README.md (subdirectories)
    6. Awesome-list style README parsing
    """
    raise NotImplementedError("extractor.extract_directives")
