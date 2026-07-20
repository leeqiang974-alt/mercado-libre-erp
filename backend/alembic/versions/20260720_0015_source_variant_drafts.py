"""bind product drafts to Amazon source variants

Revision ID: 20260720_0015
Revises: 20260720_0014
Create Date: 2026-07-20
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260720_0015"
down_revision: str | None = "20260720_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("product_drafts") as batch_op:
        batch_op.add_column(
            sa.Column(
                "source_variant_asin",
                sa.String(length=10),
                nullable=False,
                server_default="",
            )
        )
        batch_op.add_column(
            sa.Column(
                "source_variant_attributes_json",
                sa.JSON(),
                nullable=False,
                server_default="{}",
            )
        )
    op.create_index(
        "uq_product_drafts_source_variant_site",
        "product_drafts",
        ["source_product_id", "source_variant_asin", "target_site_id"],
        unique=True,
        postgresql_where=sa.text("source_variant_asin <> ''"),
        sqlite_where=sa.text("source_variant_asin <> ''"),
    )


def downgrade() -> None:
    op.drop_index("uq_product_drafts_source_variant_site", table_name="product_drafts")
    with op.batch_alter_table("product_drafts") as batch_op:
        batch_op.drop_column("source_variant_attributes_json")
        batch_op.drop_column("source_variant_asin")
