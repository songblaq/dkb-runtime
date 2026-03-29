"""Canonicalizer service — deduplicates and normalizes directives."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class CanonicalResult:
    directive_id: UUID
    preferred_name: str
    mapped_raw_count: int


async def canonicalize(
    db: AsyncSession, raw_directive_ids: list[UUID]
) -> list[CanonicalResult]:
    """Normalize raw directives into canonical directives.

    Steps:
    1. Name normalization (lowercase, strip prefixes, normalize separators)
    2. Duplicate detection (name + summary similarity)
    3. Variant detection (same tool from different sources)
    4. Create CanonicalDirective records
    5. Create RawToCanonicalMap links
    6. Create DirectiveRelation records (duplicate_of, variant_of, etc.)
    """
    raise NotImplementedError("canonicalizer.canonicalize")
