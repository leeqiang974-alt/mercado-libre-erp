"""Bind CBT listing configurations to their source draft version.

Revision ID: 20260819_0032
Revises: 20260819_0031
Create Date: 2026-08-19
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260819_0032"
down_revision: str | None = "20260819_0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "cbt_listing_configs",
        sa.Column("draft_content_version", sa.Integer(), nullable=False, server_default="1"),
    )
    # SQLite cannot drop a column default without recreating the table. The
    # retained default is harmless for local development; PostgreSQL, which is
    # required for live publishing, gets the intended application-owned value.
    if op.get_bind().dialect.name != "sqlite":
        op.alter_column("cbt_listing_configs", "draft_content_version", server_default=None)


def downgrade() -> None:
    op.drop_column("cbt_listing_configs", "draft_content_version")
