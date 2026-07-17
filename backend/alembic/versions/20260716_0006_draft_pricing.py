"""draft pricing configuration

Revision ID: 20260716_0006
Revises: 20260707_0005
Create Date: 2026-07-16
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260716_0006"
down_revision: str | None = "20260707_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    draft_columns = {column["name"] for column in inspector.get_columns("product_drafts")}
    if "source_price" not in draft_columns:
        op.add_column("product_drafts", sa.Column("source_price", sa.Float(), nullable=True))
    if "source_currency" not in draft_columns:
        op.add_column(
            "product_drafts",
            sa.Column("source_currency", sa.String(length=8), nullable=False, server_default=""),
        )
    op.execute(
        """
        UPDATE product_drafts
        SET source_price = price,
            source_currency = currency,
            price = NULL,
            currency = CASE target_site_id
                WHEN 'MLA' THEN 'ARS' WHEN 'MBO' THEN 'BOB'
                WHEN 'MLB' THEN 'BRL' WHEN 'MLC' THEN 'CLP'
                WHEN 'MCO' THEN 'COP' WHEN 'MCR' THEN 'CRC'
                WHEN 'MRD' THEN 'DOP' WHEN 'MEC' THEN 'USD'
                WHEN 'MSV' THEN 'USD' WHEN 'MGT' THEN 'GTQ'
                WHEN 'MHN' THEN 'HNL' WHEN 'MLM' THEN 'MXN'
                WHEN 'MNI' THEN 'NIO' WHEN 'MPA' THEN 'USD'
                WHEN 'MPY' THEN 'PYG' WHEN 'MPE' THEN 'PEN'
                WHEN 'MLU' THEN 'UYU' WHEN 'MLV' THEN 'VES'
                ELSE ''
            END
        WHERE source_price IS NULL
          AND (source_currency IS NULL OR source_currency = '')
          AND price IS NOT NULL
        """
    )
    if "draft_pricing_configs" not in inspector.get_table_names():
        op.create_table(
            "draft_pricing_configs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "product_draft_id",
                sa.Integer(),
                sa.ForeignKey("product_drafts.id"),
                nullable=False,
            ),
            sa.Column("source_price", sa.Float(), nullable=False),
            sa.Column("source_currency", sa.String(length=8), nullable=False),
            sa.Column("target_currency", sa.String(length=8), nullable=False),
            sa.Column("exchange_rate", sa.Float(), nullable=False),
            sa.Column("purchase_extra_cost", sa.Float(), nullable=False),
            sa.Column("shipping_cost", sa.Float(), nullable=False),
            sa.Column("platform_fee_rate", sa.Float(), nullable=False),
            sa.Column("tax_rate", sa.Float(), nullable=False),
            sa.Column("profit_margin_rate", sa.Float(), nullable=False),
            sa.Column("rounding_increment", sa.Float(), nullable=False),
            sa.Column("landed_cost", sa.Float(), nullable=False),
            sa.Column("target_price", sa.Float(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_index(
            "ix_draft_pricing_configs_product_draft_id",
            "draft_pricing_configs",
            ["product_draft_id"],
            unique=True,
        )


def downgrade() -> None:
    op.drop_index(
        "ix_draft_pricing_configs_product_draft_id",
        table_name="draft_pricing_configs",
    )
    op.drop_table("draft_pricing_configs")
    op.drop_column("product_drafts", "source_currency")
    op.drop_column("product_drafts", "source_price")
