"""CBT Global Selling listing configurations

Revision ID: 20260819_0031
Revises: 20260819_0030
Create Date: 2026-08-19
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260819_0031"
down_revision: str | None = "20260819_0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cbt_listing_configs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_draft_id", sa.Integer(), sa.ForeignKey("product_drafts.id"), nullable=False),
        sa.Column("store_id", sa.Integer(), sa.ForeignKey("stores.id"), nullable=False),
        sa.Column("category_id", sa.String(length=40), nullable=False),
        sa.Column("family_name", sa.String(length=200), nullable=False),
        sa.Column("global_title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("price_usd", sa.Float(), nullable=False),
        sa.Column("available_quantity", sa.Integer(), nullable=False),
        sa.Column("attributes_json", sa.JSON(), nullable=False),
        sa.Column("sale_terms_json", sa.JSON(), nullable=False),
        sa.Column("sites_to_sell_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_cbt_listing_configs_product_draft_id", "cbt_listing_configs", ["product_draft_id"], unique=True)
    op.create_index("ix_cbt_listing_configs_store_id", "cbt_listing_configs", ["store_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_cbt_listing_configs_store_id", table_name="cbt_listing_configs")
    op.drop_index("ix_cbt_listing_configs_product_draft_id", table_name="cbt_listing_configs")
    op.drop_table("cbt_listing_configs")
