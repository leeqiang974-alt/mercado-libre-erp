"""baseline schema

Revision ID: 20260707_0001
Revises:
Create Date: 2026-07-07
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260707_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


source_status = sa.Enum(
    "PENDING",
    "COLLECTED",
    "NEEDS_MANUAL_ACTION",
    "FAILED",
    name="sourceproductstatus",
    native_enum=False,
)
draft_status = sa.Enum(
    "DRAFT",
    "REVIEWED",
    "APPROVED",
    "PUBLISHED",
    "BLOCKED",
    name="productdraftstatus",
    native_enum=False,
)
review_decision = sa.Enum(
    "PASS",
    "NEEDS_HUMAN_REVIEW",
    "BLOCK",
    name="reviewdecision",
    native_enum=False,
)
publish_status = sa.Enum(
    "PENDING",
    "VALIDATING",
    "PUBLISHED",
    "FAILED",
    "BLOCKED",
    name="publishjobstatus",
    native_enum=False,
)


def upgrade() -> None:
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor_type", sa.String(length=40), nullable=False),
        sa.Column("actor_id", sa.String(length=120), nullable=False),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("entity_id", sa.String(length=80), nullable=False),
        sa.Column("before_json", sa.JSON(), nullable=False),
        sa.Column("after_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "source_products",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("asin", sa.String(length=20), nullable=False),
        sa.Column("raw_status", source_status, nullable=False),
        sa.Column("collected_at", sa.DateTime(), nullable=True),
        sa.Column("collection_error", sa.Text(), nullable=False),
        sa.Column("raw_snapshot_reference", sa.Text(), nullable=False),
    )
    op.create_table(
        "stores",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("marketplace", sa.String(length=40), nullable=False),
        sa.Column("site_id", sa.String(length=8), nullable=False),
        sa.Column("seller_id", sa.String(length=80), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("oauth_status", sa.String(length=40), nullable=False),
        sa.Column("token_reference", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_stores_seller_id", "stores", ["seller_id"])
    op.create_index("ix_stores_site_id", "stores", ["site_id"])
    op.create_table(
        "product_drafts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_product_id", sa.Integer(), sa.ForeignKey("source_products.id"), nullable=True),
        sa.Column("target_site_id", sa.String(length=8), nullable=False),
        sa.Column("target_category_id", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("brand", sa.String(length=120), nullable=False),
        sa.Column("condition", sa.String(length=40), nullable=False),
        sa.Column("price", sa.Float(), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("stock", sa.Integer(), nullable=False),
        sa.Column("listing_type_id", sa.String(length=40), nullable=False),
        sa.Column("shipping_profile", sa.String(length=80), nullable=False),
        sa.Column("image_urls_json", sa.JSON(), nullable=False),
        sa.Column("status", draft_status, nullable=False),
        sa.Column("risk_status", sa.String(length=40), nullable=False),
    )
    op.create_table(
        "meli_token_credentials",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("store_id", sa.Integer(), sa.ForeignKey("stores.id"), nullable=False),
        sa.Column("token_reference", sa.String(length=255), nullable=False),
        sa.Column("encrypted_access_token", sa.Text(), nullable=False),
        sa.Column("encrypted_refresh_token", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_meli_token_credentials_store_id",
        "meli_token_credentials",
        ["store_id"],
    )
    op.create_index(
        "ix_meli_token_credentials_token_reference",
        "meli_token_credentials",
        ["token_reference"],
        unique=True,
    )
    op.create_table(
        "publish_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_draft_id", sa.Integer(), sa.ForeignKey("product_drafts.id"), nullable=False),
        sa.Column("store_id", sa.Integer(), sa.ForeignKey("stores.id"), nullable=False),
        sa.Column("requested_by", sa.String(length=120), nullable=False),
        sa.Column("status", publish_status, nullable=False),
        sa.Column("request_summary_json", sa.JSON(), nullable=False),
        sa.Column("response_summary_json", sa.JSON(), nullable=False),
        sa.Column("meli_item_id", sa.String(length=80), nullable=False),
        sa.Column("permalink", sa.String(length=500), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "review_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_draft_id", sa.Integer(), sa.ForeignKey("product_drafts.id"), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("risk_level", sa.String(length=40), nullable=False),
        sa.Column("decision", review_decision, nullable=False),
        sa.Column("reasons_json", sa.JSON(), nullable=False),
        sa.Column("suggested_changes_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("review_results")
    op.drop_table("publish_jobs")
    op.drop_index("ix_meli_token_credentials_token_reference", table_name="meli_token_credentials")
    op.drop_index("ix_meli_token_credentials_store_id", table_name="meli_token_credentials")
    op.drop_table("meli_token_credentials")
    op.drop_table("product_drafts")
    op.drop_index("ix_stores_site_id", table_name="stores")
    op.drop_index("ix_stores_seller_id", table_name="stores")
    op.drop_table("stores")
    op.drop_table("source_products")
    op.drop_table("audit_events")
