from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    Numeric,
    String,
    Text,
    ForeignKey,
    Index,
    Enum,
)
from sqlalchemy.orm import relationship

from app.db.base import Base

import enum


# ============ 订单管理 ============

class OrderStatus(str, enum.Enum):
    PAYMENT_REQUIRED = "payment_required"   # 待付款
    PAID = "paid"                           # 已付款
    PACKING = "packing"                     # 备货中
    SHIPPED = "shipped"                     # 已发货
    DELIVERED = "delivered"                 # 已送达
    CANCELLED = "cancelled"                 # 已取消
    RETURNED = "returned"                   # 已退货
    REFUNDED = "refunded"                   # 已退款


class Order(Base):
    __tablename__ = "erp_orders"

    id = Column(Integer, primary_key=True)
    order_id = Column(String(64), unique=True, index=True, nullable=False)  # 美客多订单号
    site_id = Column(String(8), index=True, nullable=False)
    store_id = Column(Integer, ForeignKey("stores.id"), index=True)
    status = Column(String(32), index=True, nullable=False, default=OrderStatus.PAID.value)
    buyer_name = Column(String(256))
    buyer_email = Column(String(256))
    buyer_phone = Column(String(64))

    # 收货地址
    shipping_address = Column(Text)
    shipping_city = Column(String(128))
    shipping_state = Column(String(64))
    shipping_zip_code = Column(String(32))
    shipping_country = Column(String(8))

    # 金额
    total_amount = Column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    currency_id = Column(String(8), nullable=False, default="MXN")
    shipping_cost = Column(Numeric(12, 2), default=Decimal("0"))
    commission_fee = Column(Numeric(12, 2), default=Decimal("0"))

    # 物流
    shipping_method = Column(String(64))
    tracking_number = Column(String(128))
    tracking_url = Column(String(512))

    # 时间
    order_date = Column(DateTime, default=datetime.utcnow)
    payment_date = Column(DateTime)
    # 保留平台返回的原始时间和时区，供订单页与美客多后台逐项核对。
    order_date_source = Column(String(64))
    payment_date_source = Column(String(64))
    shipping_date = Column(DateTime)
    delivery_date = Column(DateTime)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    store = relationship("Store")

    __table_args__ = (
        Index("ix_erp_orders_site_status", "site_id", "status"),
        Index("ix_erp_orders_order_date", "order_date"),
    )


class OrderItem(Base):
    __tablename__ = "erp_order_items"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("erp_orders.id"), index=True, nullable=False)
    item_id = Column(String(64))  # 美客多商品 ID
    sku = Column(String(128), index=True)
    title = Column(String(512))
    quantity = Column(Integer, nullable=False, default=1)
    unit_price = Column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    currency_id = Column(String(8), default="MXN")
    variation_id = Column(String(64))
    variation_name = Column(String(256))
    image_url = Column(String(1024))

    order = relationship("Order", back_populates="items")


# ============ 仓库管理 ============

class Warehouse(Base):
    __tablename__ = "erp_warehouses"

    id = Column(Integer, primary_key=True)
    name = Column(String(128), nullable=False)
    code = Column(String(32), unique=True, index=True, nullable=False)
    address = Column(String(512))
    contact_name = Column(String(64))
    contact_phone = Column(String(32))
    is_active = Column(Integer, default=1)
    note = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ============ 库存管理 ============

class Inventory(Base):
    __tablename__ = "erp_inventory"

    id = Column(Integer, primary_key=True)
    sku = Column(String(128), index=True, nullable=False)
    warehouse_id = Column(Integer, ForeignKey("erp_warehouses.id"), index=True, nullable=False)
    product_name = Column(String(512))
    quantity = Column(Integer, nullable=False, default=0)
    reserved_quantity = Column(Integer, default=0)  # 已预留
    safe_stock = Column(Integer, default=0)       # 安全库存
    avg_cost = Column(Numeric(12, 2), default=Decimal("0"))  # 平均成本
    last_inbound_date = Column(DateTime)
    last_outbound_date = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    warehouse = relationship("Warehouse")

    __table_args__ = (
        Index("ix_erp_inventory_sku_warehouse", "sku", "warehouse_id", unique=True),
    )


class InventoryMovement(Base):
    __tablename__ = "erp_inventory_movements"

    id = Column(Integer, primary_key=True)
    sku = Column(String(128), index=True, nullable=False)
    warehouse_id = Column(Integer, ForeignKey("erp_warehouses.id"), index=True)
    movement_type = Column(String(32), index=True, nullable=False)  # inbound/outbound/adjustment/transfer
    quantity_change = Column(Integer, nullable=False)  # 正数入库，负数出库
    balance_after = Column(Integer)
    reference_type = Column(String(64))  # purchase_order / sales_order / adjustment
    reference_id = Column(String(128))
    remark = Column(String(512))
    operator = Column(String(64))
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


# ============ 采购管理 ============

class PurchaseStatus(str, enum.Enum):
    DRAFT = "draft"           # 草稿
    SUBMITTED = "submitted"   # 已下单
    PARTIAL = "partial"       # 部分到货
    RECEIVED = "received"     # 全部到货
    CANCELLED = "cancelled"   # 已取消


class Supplier(Base):
    __tablename__ = "erp_suppliers"

    id = Column(Integer, primary_key=True)
    name = Column(String(256), nullable=False)
    contact_name = Column(String(64))
    contact_phone = Column(String(32))
    contact_qq = Column(String(32))
    address = Column(String(512))
    note = Column(Text)
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PurchaseOrder(Base):
    __tablename__ = "erp_purchase_orders"

    id = Column(Integer, primary_key=True)
    po_number = Column(String(64), unique=True, index=True, nullable=False)
    supplier_id = Column(Integer, ForeignKey("erp_suppliers.id"), index=True)
    warehouse_id = Column(Integer, ForeignKey("erp_warehouses.id"), index=True)
    status = Column(String(32), index=True, nullable=False, default=PurchaseStatus.DRAFT.value)
    total_cost = Column(Numeric(12, 2), default=Decimal("0"))
    currency = Column(String(8), default="CNY")
    shipping_cost = Column(Numeric(12, 2), default=Decimal("0"))
    expected_date = Column(DateTime)
    note = Column(Text)
    created_by = Column(String(64))
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    supplier = relationship("Supplier")
    warehouse = relationship("Warehouse")
    items = relationship("PurchaseOrderItem", back_populates="order", cascade="all, delete-orphan")


class PurchaseOrderItem(Base):
    __tablename__ = "erp_purchase_order_items"

    id = Column(Integer, primary_key=True)
    po_id = Column(Integer, ForeignKey("erp_purchase_orders.id"), index=True, nullable=False)
    sku = Column(String(128), index=True, nullable=False)
    product_name = Column(String(512))
    quantity = Column(Integer, nullable=False)
    received_quantity = Column(Integer, default=0)
    unit_cost = Column(Numeric(12, 2), nullable=False, default=Decimal("0"))

    order = relationship("PurchaseOrder", back_populates="items")


# ============ 物流管理 ============

class ShippingStatus(str, enum.Enum):
    PENDING = "pending"       # 待发货
    PICKED = "picked"         # 已揽收
    IN_TRANSIT = "in_transit" # 运输中
    DELIVERED = "delivered"   # 已签收
    EXCEPTION = "exception"   # 异常
    RETURNED = "returned"     # 退回


class Shipment(Base):
    __tablename__ = "erp_shipments"

    id = Column(Integer, primary_key=True)
    tracking_number = Column(String(128), unique=True, index=True, nullable=False)
    order_id = Column(Integer, ForeignKey("erp_orders.id"), index=True)
    meli_order_id = Column(String(64), index=True)
    carrier = Column(String(64))  # 物流商
    shipping_method = Column(String(64))
    status = Column(String(32), index=True, nullable=False, default=ShippingStatus.PENDING.value)
    origin = Column(String(256))
    destination = Column(String(256))
    weight = Column(Numeric(8, 2))
    shipping_fee = Column(Numeric(12, 2), default=Decimal("0"))
    currency = Column(String(8), default="CNY")
    shipped_at = Column(DateTime)
    delivered_at = Column(DateTime)
    estimated_delivery = Column(DateTime)
    latest_status_text = Column(String(512))
    latest_status_time = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ============ 财务报表 ============

class ProfitRecord(Base):
    __tablename__ = "erp_profit_records"

    id = Column(Integer, primary_key=True)
    date = Column(DateTime, index=True, nullable=False)
    site_id = Column(String(8), index=True, nullable=False)
    store_id = Column(Integer, ForeignKey("stores.id"), index=True)
    order_id = Column(Integer, ForeignKey("erp_orders.id"), index=True)
    meli_order_id = Column(String(64), index=True)
    sku = Column(String(128), index=True)
    quantity = Column(Integer, default=1)

    # 收入
    sales_amount = Column(Numeric(12, 2), default=Decimal("0"))      # 销售额
    currency = Column(String(8), default="MXN")

    # 成本
    product_cost = Column(Numeric(12, 2), default=Decimal("0"))      # 商品成本
    shipping_cost = Column(Numeric(12, 2), default=Decimal("0"))     # 物流成本
    platform_fee = Column(Numeric(12, 2), default=Decimal("0"))      # 平台佣金
    payment_fee = Column(Numeric(12, 2), default=Decimal("0"))       # 支付手续费
    ad_cost = Column(Numeric(12, 2), default=Decimal("0"))           # 广告分摊
    other_cost = Column(Numeric(12, 2), default=Decimal("0"))        # 其他费用

    # 利润
    gross_profit = Column(Numeric(12, 2), default=Decimal("0"))      # 毛利
    net_profit = Column(Numeric(12, 2), default=Decimal("0"))        # 净利
    gross_margin = Column(Numeric(8, 4), default=Decimal("0"))       # 毛利率
    net_margin = Column(Numeric(8, 4), default=Decimal("0"))         # 净利率

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_erp_profit_date_site", "date", "site_id"),
    )


# ============ 每日销售统计 ============

class DailySalesStat(Base):
    __tablename__ = "erp_daily_sales_stats"

    id = Column(Integer, primary_key=True)
    date = Column(DateTime, index=True, nullable=False)
    site_id = Column(String(8), index=True, nullable=False)
    store_id = Column(Integer, ForeignKey("stores.id"), index=True)
    orders_count = Column(Integer, default=0)
    items_count = Column(Integer, default=0)
    sales_amount = Column(Numeric(12, 2), default=Decimal("0"))
    currency = Column(String(8), default="MXN")
    avg_order_value = Column(Numeric(12, 2), default=Decimal("0"))
    cancelled_orders = Column(Integer, default=0)
    refund_amount = Column(Numeric(12, 2), default=Decimal("0"))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_erp_daily_stats_date_site_store", "date", "site_id", "store_id", unique=True),
    )
