"""track publish job execution start time

Revision ID: 20260720_0009
Revises: 20260720_0008
Create Date: 2026-07-20
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260720_0009"
down_revision: str | None = "20260720_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("publish_jobs", sa.Column("started_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("publish_jobs", "started_at")
