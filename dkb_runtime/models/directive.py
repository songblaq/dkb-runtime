from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Text, text, func, Computed
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dkb_runtime.models.base import Base, jsonb_default


class CanonicalDirective(Base):
    __tablename__ = "canonical_directive"
    __table_args__ = (
        CheckConstraint("scope IN ('global','workspace','team','private')", name="directive_scope_check"),
        CheckConstraint("status IN ('active','draft','archived','deprecated')", name="directive_status_check"),
        {"schema": "dkb"},
    )

    directive_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    preferred_name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    normalized_summary: Mapped[str | None] = mapped_column(Text)
    primary_human_label: Mapped[str | None] = mapped_column(Text)
    scope: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'global'"))
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'active'"))
    canonical_meta: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text(jsonb_default))
    tsv: Mapped[str | None] = mapped_column(
        TSVECTOR,
        Computed(
            "to_tsvector('simple', coalesce(preferred_name,'') || ' ' || coalesce(normalized_summary,''))",
            persisted=True,
        ),
    )

    mappings: Mapped[list["RawToCanonicalMap"]] = relationship(back_populates="directive")
    dimension_scores: Mapped[list["DimensionScore"]] = relationship(back_populates="directive")
    verdicts: Mapped[list["Verdict"]] = relationship(back_populates="directive")
    left_relations: Mapped[list["DirectiveRelation"]] = relationship(
        back_populates="left_directive",
        foreign_keys="DirectiveRelation.left_directive_id",
    )
    right_relations: Mapped[list["DirectiveRelation"]] = relationship(
        back_populates="right_directive",
        foreign_keys="DirectiveRelation.right_directive_id",
    )
    pack_items: Mapped[list["PackItem"]] = relationship(back_populates="directive")
    embeddings: Mapped[list["DirectiveEmbedding"]] = relationship(back_populates="directive")


class RawToCanonicalMap(Base):
    __tablename__ = "raw_to_canonical_map"
    __table_args__ = (
        CheckConstraint("mapping_score >= 0 AND mapping_score <= 1", name="mapping_score_check"),
        CheckConstraint("mapping_status IN ('candidate','accepted','rejected','manual')", name="mapping_status_check"),
        {"schema": "dkb"},
    )

    mapping_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    raw_directive_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dkb.raw_directive.raw_directive_id", ondelete="CASCADE"), nullable=False
    )
    directive_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dkb.canonical_directive.directive_id", ondelete="CASCADE"), nullable=False
    )
    mapping_score: Mapped[float] = mapped_column(nullable=False)
    mapping_reason: Mapped[str | None] = mapped_column(Text)
    mapping_status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'candidate'"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    raw_directive: Mapped["RawDirective"] = relationship(back_populates="mappings")
    directive: Mapped[CanonicalDirective] = relationship(back_populates="mappings")


class DirectiveRelation(Base):
    __tablename__ = "directive_relation"
    __table_args__ = (
        CheckConstraint(
            "relation_type IN ('duplicate_of','variant_of','complements','conflicts_with','supersedes','bundle_member_of','derived_from')",
            name="directive_relation_type_check",
        ),
        CheckConstraint("strength >= 0 AND strength <= 1", name="directive_relation_strength_check"),
        CheckConstraint("left_directive_id <> right_directive_id", name="directive_relation_not_same_check"),
        {"schema": "dkb"},
    )

    relation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    left_directive_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dkb.canonical_directive.directive_id", ondelete="CASCADE"), nullable=False
    )
    relation_type: Mapped[str] = mapped_column(Text, nullable=False)
    right_directive_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dkb.canonical_directive.directive_id", ondelete="CASCADE"), nullable=False
    )
    strength: Mapped[float | None] = mapped_column(server_default=text("0.500"))
    explanation: Mapped[str | None] = mapped_column(Text)
    relation_meta: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text(jsonb_default))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    left_directive: Mapped[CanonicalDirective] = relationship(
        back_populates="left_relations", foreign_keys=[left_directive_id]
    )
    right_directive: Mapped[CanonicalDirective] = relationship(
        back_populates="right_relations", foreign_keys=[right_directive_id]
    )


from dkb_runtime.models.source import RawDirective  # noqa: E402
from dkb_runtime.models.scoring import DimensionScore, DirectiveEmbedding  # noqa: E402
from dkb_runtime.models.verdict import Verdict, PackItem  # noqa: E402
