"""store operator CNY costs for Global Selling pricing

Revision ID: 20260819_0035
Revises: 20260819_0034
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260819_0035"
down_revision: str | None = "20260819_0034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | None = None


def upgrade() -> None:
    with op.batch_alter_table("draft_pricing_configs") as batch_op:
        batch_op.add_column(sa.Column("cost_currency", sa.String(length=8), nullable=False, server_default="CNY"))
        batch_op.add_column(sa.Column("purchase_cost", sa.Float(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("domestic_shipping_cost", sa.Float(), nullable=False, server_default="0"))


def downgrade() -> None:
    with op.batch_alter_table("draft_pricing_configs") as batch_op:
        batch_op.drop_column("domestic_shipping_cost")
        batch_op.drop_column("purchase_cost")
        batch_op.drop_column("cost_currency")
