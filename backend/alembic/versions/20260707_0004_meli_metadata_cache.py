"""meli metadata cache

Revision ID: 20260707_0004
Revises: 20260707_0003
Create Date: 2026-07-07
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260707_0004"
down_revision: str | None = "20260707_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "meli_metadata_cache",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cache_key", sa.String(length=160), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("refreshed_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_meli_metadata_cache_cache_key",
        "meli_metadata_cache",
        ["cache_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_meli_metadata_cache_cache_key", table_name="meli_metadata_cache")
    op.drop_table("meli_metadata_cache")
