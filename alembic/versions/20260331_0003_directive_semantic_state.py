"""Add directive_semantic_state table.

Revision ID: 20260331_0003
Revises: 20260331_0002
Create Date: 2026-03-31 12:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision = "20260331_0003"
down_revision = "20260331_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "directive_semantic_state",
        sa.Column("state_id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "directive_id",
            UUID(as_uuid=True),
            sa.ForeignKey("dkb.canonical_directive.directive_id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("concept_vector", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("trust_state", sa.String(length=64), nullable=True),
        sa.Column("lifecycle_phase", sa.String(length=64), nullable=True),
        sa.Column("related_directive_ids", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("last_updated", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        schema="dkb",
    )


def downgrade() -> None:
    op.drop_table("directive_semantic_state", schema="dkb")
