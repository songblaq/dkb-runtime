"""Add score_cache and llm_usage_log tables.

Revision ID: 20260331_0002
Revises: 20260329_0001
Create Date: 2026-03-31 00:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision = "20260331_0002"
down_revision = "20260329_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "score_cache",
        sa.Column("cache_id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "directive_id",
            UUID(as_uuid=True),
            sa.ForeignKey("dkb.canonical_directive.directive_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "dimension_model_id",
            UUID(as_uuid=True),
            sa.ForeignKey("dkb.dimension_model.dimension_model_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("fusion_config_id", sa.Text(), nullable=False),
        sa.Column("scores_json", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "directive_id",
            "dimension_model_id",
            "provider",
            "fusion_config_id",
            name="uq_score_cache_lookup",
        ),
        schema="dkb",
    )
    op.create_table(
        "llm_usage_log",
        sa.Column("log_id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("request_id", sa.Text(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("cost_usd", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        schema="dkb",
    )
    op.create_index("ix_llm_usage_log_created_at", "llm_usage_log", ["created_at"], schema="dkb")


def downgrade() -> None:
    op.drop_index("ix_llm_usage_log_created_at", table_name="llm_usage_log", schema="dkb")
    op.drop_table("llm_usage_log", schema="dkb")
    op.drop_table("score_cache", schema="dkb")
