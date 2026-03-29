from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, Computed, DateTime, ForeignKey, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dkb_runtime.models.base import Base, jsonb_default

if TYPE_CHECKING:
    from dkb_runtime.models.directive import RawToCanonicalMap


class Source(Base):
    __tablename__ = "source"
    __table_args__ = (
        CheckConstraint(
            "source_kind IN ('git_repo','local_folder','archive','manual_upload','web_page')",
            name="source_kind_check",
        ),
        {"schema": "dkb"},
    )

    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_kind: Mapped[str] = mapped_column(Text, nullable=False)
    origin_uri: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    owner_name: Mapped[str | None] = mapped_column(Text)
    canonical_source_name: Mapped[str | None] = mapped_column(Text)
    provenance_hint: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, server_default=text(jsonb_default))

    snapshots: Mapped[list[SourceSnapshot]] = relationship(back_populates="source", cascade="all, delete-orphan")


class SourceSnapshot(Base):
    __tablename__ = "source_snapshot"
    __table_args__ = (
        CheckConstraint(
            "revision_type IN ('commit','tag','branch','digest','manual_version','none')",
            name="snapshot_revision_type_check",
        ),
        CheckConstraint(
            "capture_status IN ('captured','partial','failed')",
            name="snapshot_capture_status_check",
        ),
        {"schema": "dkb"},
    )

    snapshot_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dkb.source.source_id", ondelete="CASCADE"), nullable=False
    )
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    revision_ref: Mapped[str | None] = mapped_column(Text)
    revision_type: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'none'"))
    checksum: Mapped[str | None] = mapped_column(Text)
    license_text: Mapped[str | None] = mapped_column(Text)
    raw_blob_uri: Mapped[str | None] = mapped_column(Text)
    capture_status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'captured'"))
    snapshot_meta: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text(jsonb_default))

    source: Mapped[Source] = relationship(back_populates="snapshots")
    raw_directives: Mapped[list[RawDirective]] = relationship(
        back_populates="snapshot",
        cascade="all, delete-orphan",
    )


class RawDirective(Base):
    __tablename__ = "raw_directive"
    __table_args__ = (
        CheckConstraint(
            "content_format IN ('markdown','yaml','json','text','html','unknown')",
            name="raw_directive_content_format_check",
        ),
        {"schema": "dkb"},
    )

    raw_directive_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dkb.source_snapshot.snapshot_id", ondelete="CASCADE"),
        nullable=False,
    )
    raw_name: Mapped[str] = mapped_column(Text, nullable=False)
    entry_path: Mapped[str | None] = mapped_column(Text)
    declared_type: Mapped[str | None] = mapped_column(Text)
    content_format: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'markdown'"))
    language_code: Mapped[str | None] = mapped_column(Text, server_default=text("'en'"))
    summary_raw: Mapped[str | None] = mapped_column(Text)
    body_raw: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, server_default=text(jsonb_default))
    tsv: Mapped[str | None] = mapped_column(
        TSVECTOR,
        Computed(
            "to_tsvector('simple', coalesce(raw_name,'') || ' ' || coalesce(summary_raw,'') || ' ' || coalesce(body_raw,''))",
            persisted=True,
        ),
    )

    snapshot: Mapped[SourceSnapshot] = relationship(back_populates="raw_directives")
    evidence_items: Mapped[list[Evidence]] = relationship(back_populates="raw_directive", cascade="all, delete-orphan")
    mappings: Mapped[list[RawToCanonicalMap]] = relationship(
        back_populates="raw_directive", cascade="all, delete-orphan"
    )


class Evidence(Base):
    __tablename__ = "evidence"
    __table_args__ = (
        CheckConstraint(
            "evidence_kind IN ('summary','role_phrase','input_output','usage_example','license_excerpt','install_note','tool_reference','source_signal','activity_signal','manual_note')",
            name="evidence_kind_check",
        ),
        CheckConstraint("weight_hint >= 0 AND weight_hint <= 1", name="evidence_weight_hint_check"),
        {"schema": "dkb"},
    )

    evidence_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    raw_directive_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dkb.raw_directive.raw_directive_id", ondelete="CASCADE"),
        nullable=False,
    )
    evidence_kind: Mapped[str] = mapped_column(Text, nullable=False)
    excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    location_ref: Mapped[str | None] = mapped_column(Text)
    weight_hint: Mapped[float | None] = mapped_column(nullable=True, server_default=text("0.500"))
    evidence_meta: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text(jsonb_default))

    raw_directive: Mapped[RawDirective] = relationship(back_populates="evidence_items")
