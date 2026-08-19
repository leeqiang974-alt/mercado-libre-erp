"""add image URL to ERP order items

Revision ID: 20260819_0029
Revises: 20260721_0028
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

from app.models.erp import (
    DailySalesStat,
    Inventory,
    InventoryMovement,
    Order,
    OrderItem,
    ProfitRecord,
    PurchaseOrder,
    PurchaseOrderItem,
    Shipment,
    Supplier,
    Warehouse,
)

revision: str = "20260819_0029"
down_revision: str | None = "20260721_0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    erp_tables = [
        Order.__table__,
        OrderItem.__table__,
        Warehouse.__table__,
        Inventory.__table__,
        InventoryMovement.__table__,
        Supplier.__table__,
        PurchaseOrder.__table__,
        PurchaseOrderItem.__table__,
        Shipment.__table__,
        ProfitRecord.__table__,
        DailySalesStat.__table__,
    ]
    # ERP 数据模型是在既有基础项目之后加入的。新环境先创建整套 ERP 表，
    # 已运行环境只补缺失的图片字段，不会改写现有订单。
    sa.MetaData().create_all(bind=bind, tables=erp_tables, checkfirst=True)

    columns = {column["name"] for column in sa.inspect(bind).get_columns("erp_order_items")}
    if "image_url" not in columns:
        op.add_column("erp_order_items", sa.Column("image_url", sa.String(length=1024), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("erp_order_items")}
    if "image_url" in columns:
        op.drop_column("erp_order_items", "image_url")
