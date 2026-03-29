from __future__ import annotations

import uuid
from datetime import datetime

from pgvector.sqlalchemy import VECTOR
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dkb_runtime.models.base import Base, jsonb_default


class DimensionModel(Base):
    __tablename__ = "dimension_model"
    __table_args__ = ({"schema": "dkb"},)

    dimension_model_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    version: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text(jsonb_default))
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    scores: Mapped[list[DimensionScore]] = relationship(back_populates="dimension_model")
    verdicts: Mapped[list[Verdict]] = relationship(back_populates="dimension_model")


class DimensionScore(Base):
    __tablename__ = "dimension_score"
    __table_args__ = (
        CheckConstraint("score >= 0 AND score <= 1", name="dimension_score_value_check"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="dimension_score_confidence_check"),
        {"schema": "dkb"},
    )

    dimension_score_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
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
    dimension_group: Mapped[str] = mapped_column(Text, nullable=False)
    dimension_key: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[float] = mapped_column(nullable=False)
    confidence: Mapped[float] = mapped_column(nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text)
    features: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text(jsonb_default))
    scored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    directive: Mapped[CanonicalDirective] = relationship(back_populates="dimension_scores")
    dimension_model: Mapped[DimensionModel] = relationship(back_populates="scores")


class DirectiveEmbedding(Base):
    __tablename__ = "directive_embedding"
    __table_args__ = ({"schema": "dkb"},)

    directive_embedding_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    directive_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dkb.canonical_directive.directive_id", ondelete="CASCADE"),
        nullable=False,
    )
    embedding_model: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_dimensions: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1536"))
    embedding: Mapped[list[float]] = mapped_column(VECTOR(1536), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    directive: Mapped[CanonicalDirective] = relationship(back_populates="embeddings")


from dkb_runtime.models.directive import CanonicalDirective  # noqa: E402
from dkb_runtime.models.verdict import Verdict  # noqa: E402
