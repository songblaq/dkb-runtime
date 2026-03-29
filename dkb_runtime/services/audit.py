"""Audit service — logs operations for traceability."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from dkb_runtime.models import AuditEvent


def log_audit(
    db: Session,
    object_kind: str,
    object_id: UUID,
    action: str,
    payload: dict | None = None,
) -> None:
    """Record an audit event."""
    event = AuditEvent(
        object_kind=object_kind,
        object_id=object_id,
        action=action,
        payload=payload or {},
    )
    db.add(event)
    db.flush()
