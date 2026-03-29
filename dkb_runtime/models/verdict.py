from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dkb_runtime.models.base import Base, jsonb_default


class Verdict(Base):
    __tablename__ = "verdict"
    __table_args__ = (
        CheckConstraint(
            "provenance_state IN ('official','vendor','community','individual','unknown')",
            name="verdict_provenance_state_check",
        ),
        CheckConstraint(
            "trust_state IN ('unknown','reviewing','verified','caution','blocked')",
            name="verdict_trust_state_check",
        ),
        CheckConstraint(
            "legal_state IN ('clear','custom','no_license','removed','restricted')",
            name="verdict_legal_state_check",
        ),
        CheckConstraint(
            "lifecycle_state IN ('active','stale','dormant','archived','disappeared')",
            name="verdict_lifecycle_state_check",
        ),
        CheckConstraint(
            "recommendation_state IN ('candidate','preferred','merged','excluded','deprecated')",
            name="verdict_recommendation_state_check",
        ),
        {"schema": "dkb"},
    )

    verdict_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    directive_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dkb.canonical_directive.directive_id", ondelete="CASCADE"),
        nullable=False,
    )
    dimension_model_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dkb.dimension_model.dimension_model_id", ondelete="CASCADE"),
        nullable=False,
    )
    provenance_state: Mapped[str] = mapped_column(Text, nullable=False)
    trust_state: Mapped[str] = mapped_column(Text, nullable=False)
    legal_state: Mapped[str] = mapped_column(Text, nullable=False)
    lifecycle_state: Mapped[str] = mapped_column(Text, nullable=False)
    recommendation_state: Mapped[str] = mapped_column(Text, nullable=False)
    verdict_reason: Mapped[str | None] = mapped_column(Text)
    policy_trace: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text(jsonb_default))
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    directive: Mapped[CanonicalDirective] = relationship(back_populates="verdicts")
    dimension_model: Mapped[DimensionModel] = relationship(back_populates="verdicts")


class Pack(Base):
    __tablename__ = "pack"
    __table_args__ = (
        CheckConstraint(
            "pack_type IN ('safe','lean','starter','role','experimental','custom')",
            name="pack_type_check",
        ),
        CheckConstraint("status IN ('draft','active','deprecated')", name="pack_status_check"),
        {"schema": "dkb"},
    )

    pack_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pack_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    pack_name: Mapped[str] = mapped_column(Text, nullable=False)
    pack_goal: Mapped[str] = mapped_column(Text, nullable=False)
    pack_type: Mapped[str] = mapped_column(Text, nullable=False)
    selection_policy: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text(jsonb_default))
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'draft'"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    items: Mapped[list[PackItem]] = relationship(back_populates="pack", cascade="all, delete-orphan")


class PackItem(Base):
    __tablename__ = "pack_item"
    __table_args__ = (
        CheckConstraint("priority_weight >= 0 AND priority_weight <= 1", name="pack_item_priority_weight_check"),
        {"schema": "dkb"},
    )

    pack_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pack_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dkb.pack.pack_id", ondelete="CASCADE"), nullable=False
    )
    directive_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dkb.canonical_directive.directive_id", ondelete="CASCADE"),
        nullable=False,
    )
    inclusion_reason: Mapped[str | None] = mapped_column(Text)
    priority_weight: Mapped[float | None] = mapped_column(server_default=text("0.500"))
    role_fit: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text(jsonb_default))

    pack: Mapped[Pack] = relationship(back_populates="items")
    directive: Mapped[CanonicalDirective] = relationship(back_populates="pack_items")


class AuditEvent(Base):
    __tablename__ = "audit_event"
    __table_args__ = ({"schema": "dkb"},)

    audit_event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    object_kind: Mapped[str] = mapped_column(Text, nullable=False)
    object_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    action: Mapped[str] = mapped_column(Text, nullable=False)
    actor: Mapped[str | None] = mapped_column(Text, server_default=text("'system'"))
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text(jsonb_default))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


from dkb_runtime.models.directive import CanonicalDirective  # noqa: E402
from dkb_runtime.models.scoring import DimensionModel  # noqa: E402
