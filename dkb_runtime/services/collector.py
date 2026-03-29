"""Collector service — acquires source snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class SnapshotResult:
    snapshot_id: UUID
    revision_ref: str
    capture_status: str
    raw_blob_uri: str


async def collect_source(db: AsyncSession, source_id: UUID) -> SnapshotResult:
    """Clone/fetch a source and create a snapshot record.

    Steps:
    1. Look up the source by ID
    2. Clone (shallow) or pull the repo to storage/snapshots/{source_id}/{snapshot_id}/
    3. Compute checksum (git HEAD SHA)
    4. Detect license files
    5. Create SourceSnapshot record
    6. Log audit event
    """
    raise NotImplementedError("collector.collect_source")
