"""Audit service — logs operations for traceability."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession


async def log_audit(
    db: AsyncSession,
    object_kind: str,
    object_id: UUID,
    action: str,
    payload: dict | None = None,
) -> None:
    """Record an audit event.

    Args:
        object_kind: e.g. "source", "snapshot", "directive", "verdict", "pack"
        object_id: UUID of the affected object
        action: e.g. "collected", "extracted", "scored", "verdicted", "packed", "exported"
        payload: optional JSON payload with details
    """
    raise NotImplementedError("audit.log_audit")
