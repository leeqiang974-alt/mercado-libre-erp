"""bind approvals and reviews to draft content versions

Revision ID: 20260716_0007
Revises: 20260716_0006
Create Date: 2026-07-16
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260716_0007"
down_revision: str | None = "20260716_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "product_drafts",
        sa.Column("content_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "product_draft_approvals",
        sa.Column("draft_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "review_results",
        sa.Column("draft_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column("publish_jobs", sa.Column("idempotency_key", sa.String(length=64)))
    op.execute(
        "UPDATE publish_jobs SET idempotency_key = "
        "'legacy-' || CAST(id AS VARCHAR) WHERE idempotency_key IS NULL"
    )
    op.alter_column("publish_jobs", "idempotency_key", nullable=False)
    op.create_index(
        "ix_publish_jobs_idempotency_key",
        "publish_jobs",
        ["idempotency_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_publish_jobs_idempotency_key", table_name="publish_jobs")
    op.drop_column("publish_jobs", "idempotency_key")
    op.drop_column("review_results", "draft_version")
    op.drop_column("product_draft_approvals", "draft_version")
    op.drop_column("product_drafts", "content_version")
