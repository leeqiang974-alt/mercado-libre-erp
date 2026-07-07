"""draft listing configs

Revision ID: 20260707_0003
Revises: 20260707_0002
Create Date: 2026-07-07
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260707_0003"
down_revision: str | None = "20260707_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "draft_listing_configs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_draft_id", sa.Integer(), sa.ForeignKey("product_drafts.id"), nullable=False),
        sa.Column("site_id", sa.String(length=8), nullable=False),
        sa.Column("category_id", sa.String(length=40), nullable=False),
        sa.Column("listing_type_id", sa.String(length=40), nullable=False),
        sa.Column("fulfillment", sa.String(length=40), nullable=False),
        sa.Column("attributes_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_draft_listing_configs_product_draft_id",
        "draft_listing_configs",
        ["product_draft_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_draft_listing_configs_product_draft_id",
        table_name="draft_listing_configs",
    )
    op.drop_table("draft_listing_configs")
