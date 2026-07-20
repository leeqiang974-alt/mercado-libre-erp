"""require explicit listing inventory confirmation

Revision ID: 20260721_0027
Revises: 20260721_0026
Create Date: 2026-07-21
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260721_0027"
down_revision: str | None = "20260721_0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "draft_listing_configs",
        sa.Column("available_quantity", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("draft_listing_configs", "available_quantity")
