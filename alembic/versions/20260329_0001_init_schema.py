"""Initialize DKB schema from canonical SQL.

Revision ID: 20260329_0001
Revises:
Create Date: 2026-03-29 00:00:00
"""

from __future__ import annotations

from pathlib import Path

from alembic import op

revision = "20260329_0001"
down_revision = None
branch_labels = None
depends_on = None


def _read_sql(filename: str) -> str:
    root = Path(__file__).resolve().parents[2]
    return (root / "schema" / filename).read_text(encoding="utf-8")


def upgrade() -> None:
    op.execute(_read_sql("01_dkb_postgresql_v0_1.sql"))


def downgrade() -> None:
    op.execute("DROP SCHEMA IF EXISTS dkb CASCADE;")
