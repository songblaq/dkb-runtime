from __future__ import annotations

from uuid import uuid4

from sqlalchemy import func, select

from dkb_runtime.models import AuditEvent
from dkb_runtime.services.audit import log_audit


def test_log_audit_creates_event(db):
    oid = uuid4()
    log_audit(db, "source", oid, "collected", {"k": "v"})
    db.commit()
    row = db.scalars(select(AuditEvent).where(AuditEvent.object_id == oid)).one()
    assert row.object_kind == "source"
    assert row.action == "collected"
    assert row.payload == {"k": "v"}


def test_log_audit_none_payload_defaults_empty(db):
    oid = uuid4()
    log_audit(db, "pack", oid, "packed", None)
    db.commit()
    row = db.scalars(select(AuditEvent).where(AuditEvent.object_id == oid)).one()
    assert row.payload == {}


def test_log_audit_object_kinds(db):
    for kind in ("source", "snapshot", "directive", "verdict", "pack"):
        oid = uuid4()
        log_audit(db, kind, oid, "test", {})
        db.commit()
        n = db.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.object_id == oid))
        assert n == 1
