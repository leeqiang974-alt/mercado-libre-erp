"""expand review cost precision

Revision ID: 20260721_0024
Revises: 20260721_0023
Create Date: 2026-07-21
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260721_0024"
down_revision: str | None = "20260721_0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("review_results") as batch_op:
        batch_op.alter_column(
            "estimated_cost_amount",
            existing_type=sa.Numeric(18, 8),
            type_=sa.Numeric(28, 8),
            existing_nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("review_results") as batch_op:
        batch_op.alter_column(
            "estimated_cost_amount",
            existing_type=sa.Numeric(28, 8),
            type_=sa.Numeric(18, 8),
            existing_nullable=True,
        )
