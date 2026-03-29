"""Pack engine — builds curated packs from scored/verdicted directives."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session


@dataclass
class PackBuildResult:
    pack_id: UUID
    pack_name: str
    item_count: int
    status: str


def build_pack(db: Session, pack_id: UUID) -> PackBuildResult:
    """Build a curated pack based on its selection policy.

    Steps:
    1. Load pack definition and selection_policy
    2. Query directives matching filters (trust, legal, score minimums)
    3. Exclude by recommendation_state
    4. Rank by pack_utility function
    5. Create PackItem records
    6. Set pack status to active
    """
    raise NotImplementedError("pack_engine.build_pack")
