"""collection jobs

Revision ID: 20260707_0002
Revises: 20260707_0001
Create Date: 2026-07-07
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260707_0002"
down_revision: str | None = "20260707_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


collection_status = sa.Enum(
    "PENDING",
    "RUNNING",
    "COMPLETED",
    "NEEDS_MANUAL_ACTION",
    "FAILED",
    name="collectionjobstatus",
    native_enum=False,
)


def upgrade() -> None:
    op.create_table(
        "collection_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("target_site_id", sa.String(length=8), nullable=False),
        sa.Column("status", collection_status, nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("source_product_id", sa.Integer(), sa.ForeignKey("source_products.id"), nullable=True),
        sa.Column("draft_id", sa.Integer(), sa.ForeignKey("product_drafts.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("collection_jobs")
