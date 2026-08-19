"""Normalize legacy collection job status values.

Revision ID: 20260819_0033
Revises: 20260819_0032
Create Date: 2026-08-19
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260819_0033"
down_revision: str | None = "20260819_0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE collection_jobs SET status = LOWER(status)"))


def downgrade() -> None:
    # Status values are intentionally kept canonical and lowercase.
    pass
