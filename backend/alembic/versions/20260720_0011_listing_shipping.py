"""persist selected non-FULL shipping option

Revision ID: 20260720_0011
Revises: 20260720_0010
Create Date: 2026-07-20
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260720_0011"
down_revision: str | None = "20260720_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "draft_listing_configs",
        sa.Column("shipping_mode", sa.String(length=40), nullable=False, server_default=""),
    )
    op.add_column(
        "draft_listing_configs",
        sa.Column(
            "shipping_logistic_type",
            sa.String(length=40),
            nullable=False,
            server_default="",
        ),
    )


def downgrade() -> None:
    op.drop_column("draft_listing_configs", "shipping_logistic_type")
    op.drop_column("draft_listing_configs", "shipping_mode")
