"""add versioned provider model prices and review cost snapshots

Revision ID: 20260721_0022
Revises: 20260720_0021
Create Date: 2026-07-21
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260721_0022"
down_revision: str | None = "20260720_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "provider_model_prices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("model", sa.String(length=160), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("input_price_per_million", sa.Numeric(18, 6), nullable=False),
        sa.Column("output_price_per_million", sa.Numeric(18, 6), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider", "model", "version", name="uq_provider_model_price_version"
        ),
    )
    op.create_index(
        op.f("ix_provider_model_prices_provider"),
        "provider_model_prices",
        ["provider"],
        unique=False,
    )
    op.create_index(
        op.f("ix_provider_model_prices_model"),
        "provider_model_prices",
        ["model"],
        unique=False,
    )
    op.create_index(
        op.f("ix_provider_model_prices_active"),
        "provider_model_prices",
        ["active"],
        unique=False,
    )
    with op.batch_alter_table("review_results") as batch_op:
        batch_op.add_column(sa.Column("price_config_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("estimated_cost_amount", sa.Numeric(18, 8), nullable=True))
        batch_op.add_column(
            sa.Column("estimated_cost_currency", sa.String(length=3), nullable=False, server_default="")
        )
        batch_op.create_foreign_key(
            "fk_review_results_price_config_id_provider_model_prices",
            "provider_model_prices",
            ["price_config_id"],
            ["id"],
        )
        batch_op.alter_column("estimated_cost_currency", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("review_results") as batch_op:
        batch_op.drop_constraint(
            "fk_review_results_price_config_id_provider_model_prices", type_="foreignkey"
        )
        batch_op.drop_column("estimated_cost_currency")
        batch_op.drop_column("estimated_cost_amount")
        batch_op.drop_column("price_config_id")
    op.drop_index(op.f("ix_provider_model_prices_active"), table_name="provider_model_prices")
    op.drop_index(op.f("ix_provider_model_prices_model"), table_name="provider_model_prices")
    op.drop_index(op.f("ix_provider_model_prices_provider"), table_name="provider_model_prices")
    op.drop_table("provider_model_prices")
