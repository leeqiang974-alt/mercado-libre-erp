"""persist structured Amazon source measurements

Revision ID: 20260720_0019
Revises: 20260720_0018
Create Date: 2026-07-20
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260720_0019"
down_revision: str | None = "20260720_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("source_products") as batch_op:
        batch_op.add_column(
            sa.Column("measurements_json", sa.JSON(), nullable=False, server_default="{}")
        )


def downgrade() -> None:
    with op.batch_alter_table("source_products") as batch_op:
        batch_op.drop_column("measurements_json")
