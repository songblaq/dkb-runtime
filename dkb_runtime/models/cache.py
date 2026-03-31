from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from dkb_runtime.models.base import Base, jsonb_default


class ScoreCache(Base):
    __tablename__ = "score_cache"
    __table_args__ = (
        UniqueConstraint(
            "directive_id",
            "dimension_model_id",
            "provider",
            "fusion_config_id",
            name="uq_score_cache_lookup",
        ),
        {"schema": "dkb"},
    )

    cache_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
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
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    fusion_config_id: Mapped[str] = mapped_column(Text, nullable=False)
    scores_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text(jsonb_default))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class LLMUsageLog(Base):
    __tablename__ = "llm_usage_log"
    __table_args__ = ({"schema": "dkb"},)

    log_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    input_tokens: Mapped[int] = mapped_column(nullable=False)
    output_tokens: Mapped[int] = mapped_column(nullable=False)
    cost_usd: Mapped[float] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
