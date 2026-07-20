"""add review execution metadata

Revision ID: 20260720_0013
Revises: 20260720_0012
Create Date: 2026-07-20
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260720_0013"
down_revision: str | None = "20260720_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("review_results") as batch_op:
        batch_op.add_column(
            sa.Column("prompt_version", sa.String(length=80), nullable=False, server_default="")
        )
        batch_op.add_column(
            sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column(
                "provider_status",
                sa.String(length=40),
                nullable=False,
                server_default="completed",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("review_results") as batch_op:
        batch_op.drop_column("provider_status")
        batch_op.drop_column("duration_ms")
        batch_op.drop_column("prompt_version")
