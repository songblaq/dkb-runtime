from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from dkb_runtime.models.base import Base


class DirectiveSemanticState(Base):
    """Persisted semantic / concept snapshot for a canonical directive (production concept layer)."""

    __tablename__ = "directive_semantic_state"
    __table_args__ = ({"schema": "dkb"},)

    state_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    directive_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dkb.canonical_directive.directive_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    concept_vector: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    trust_state: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lifecycle_phase: Mapped[str | None] = mapped_column(String(64), nullable=True)
    related_directive_ids: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
