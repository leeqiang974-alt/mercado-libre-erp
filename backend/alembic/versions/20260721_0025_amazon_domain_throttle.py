"""add persistent Amazon domain throttling

Revision ID: 20260721_0025
Revises: 20260721_0024
Create Date: 2026-07-21
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260721_0025"
down_revision: str | None = "20260721_0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "collection_jobs",
        sa.Column("next_attempt_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "amazon_domain_throttles",
        sa.Column("domain", sa.String(length=64), nullable=False),
        sa.Column("next_allowed_at", sa.DateTime(), nullable=True),
        sa.Column("backoff_until", sa.DateTime(), nullable=True),
        sa.Column("consecutive_challenges", sa.Integer(), nullable=False),
        sa.Column("last_request_at", sa.DateTime(), nullable=True),
        sa.Column("last_outcome", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("domain"),
    )
    op.create_index(
        "ix_collection_jobs_pending_schedule",
        "collection_jobs",
        ["status", "next_attempt_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_collection_jobs_pending_schedule", table_name="collection_jobs")
    op.drop_table("amazon_domain_throttles")
    op.drop_column("collection_jobs", "next_attempt_at")
