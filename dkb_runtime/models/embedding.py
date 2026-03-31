from __future__ import annotations

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Integer, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dkb_runtime.models.base import Base


class DirectiveEmbedding(Base):
    """Vector embedding row for a canonical directive (pgvector)."""

    __tablename__ = "directive_embedding"
    __table_args__ = ({"schema": "dkb"},)

    embedding_id: Mapped[uuid.UUID] = mapped_column(
        "directive_embedding_id",
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    directive_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dkb.canonical_directive.directive_id", ondelete="CASCADE"),
        nullable=False,
    )
    embedding = mapped_column(Vector(1536), nullable=False)
    model_name: Mapped[str] = mapped_column("embedding_model", Text, nullable=False)
    embedding_dim: Mapped[int] = mapped_column(
        "embedding_dimensions",
        Integer,
        nullable=False,
        server_default=text("1536"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    directive: Mapped[CanonicalDirective] = relationship(back_populates="embeddings")


from dkb_runtime.models.directive import CanonicalDirective  # noqa: E402
