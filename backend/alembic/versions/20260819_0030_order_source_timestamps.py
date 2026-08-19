"""preserve original Mercado Libre order timestamps

Revision ID: 20260819_0030
Revises: 20260819_0029
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260819_0030"
down_revision: str | None = "20260819_0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("erp_orders")}
    if "order_date_source" not in columns:
        op.add_column("erp_orders", sa.Column("order_date_source", sa.String(length=64), nullable=True))
    if "payment_date_source" not in columns:
        op.add_column("erp_orders", sa.Column("payment_date_source", sa.String(length=64), nullable=True))


def downgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("erp_orders")}
    if "payment_date_source" in columns:
        op.drop_column("erp_orders", "payment_date_source")
    if "order_date_source" in columns:
        op.drop_column("erp_orders", "order_date_source")
