"""add operational controls for connected stores

Revision ID: 20260826_0022
Revises: 20260824_0021
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260826_0022"
down_revision: str | None = "20260824_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("stores", sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()))


def downgrade() -> None:
    op.drop_column("stores", "is_enabled")
