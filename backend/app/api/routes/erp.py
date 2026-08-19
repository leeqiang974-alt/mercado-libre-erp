from datetime import datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models.erp import (
    Order,
    OrderItem,
    Warehouse,
    Inventory,
    InventoryMovement,
    PurchaseOrder,
    PurchaseOrderItem,
    Supplier,
    Shipment,
    ProfitRecord,
    DailySalesStat,
)
from app.models.product_draft import ProductDraft
from app.models.publish_job import PublishJob
from app.models.store import Store

router = APIRouter(prefix="/api/erp", tags=["erp"])

settings = get_settings()


def _utc_iso(value: datetime | None) -> str | None:
    return f"{value.isoformat()}Z" if value else None


# ============ 统计概览 ============

@router.get("/overview")
def erp_overview(db: Session = Depends(get_db)):
    """ERP 首页统计概览"""
    # 订单数
    today = datetime.utcnow().date()
    today_start = datetime.combine(today, datetime.min.time())

    total_orders = db.query(func.count(Order.id)).scalar() or 0
    today_orders = db.query(func.count(Order.id)).filter(Order.order_date >= today_start).scalar() or 0
    pending_orders = db.query(func.count(Order.id)).filter(Order.status == "paid").scalar() or 0

    # 销售金额
    total_sales = db.query(func.coalesce(func.sum(Order.total_amount), Decimal("0"))).scalar()
    today_sales = db.query(func.coalesce(func.sum(Order.total_amount), Decimal("0"))).filter(
        Order.order_date >= today_start
    ).scalar()

    # 库存
    total_skus = db.query(func.count(Inventory.id)).scalar() or 0
    low_stock_skus = db.query(func.count(Inventory.id)).filter(
        Inventory.quantity < Inventory.safe_stock,
        Inventory.safe_stock > 0,
    ).scalar() or 0

    # 待发货
    pending_shipment = db.query(func.count(Shipment.id)).filter(
        Shipment.status == "pending"
    ).scalar() or 0

    # 店铺与商品（真实数据）
    total_stores = db.query(func.count(Store.id)).filter(Store.oauth_status == "connected").scalar() or 0
    total_drafts = db.query(func.count(ProductDraft.id)).scalar() or 0
    pending_publish = db.query(func.count(PublishJob.id)).filter(PublishJob.status == "pending").scalar() or 0
    published_count = db.query(func.count(PublishJob.id)).filter(PublishJob.status == "success").scalar() or 0

    return {
        "total_orders": total_orders,
        "today_orders": today_orders,
        "pending_orders": pending_orders,
        "total_sales": str(total_sales),
        "today_sales": str(today_sales),
        "total_skus": total_skus,
        "low_stock_skus": low_stock_skus,
        "pending_shipment": pending_shipment,
        "currency": "MXN",
        # 真实业务数据
        "total_stores": total_stores,
        "total_drafts": total_drafts,
        "pending_publish": pending_publish,
        "published_count": published_count,
    }


# ============ 订单管理 ============

@router.get("/orders")
def list_orders(
    status: str = Query(None),
    site_id: str = Query(None),
    keyword: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """订单列表"""
    query = db.query(Order)
    if status:
        query = query.filter(Order.status == status)
    if site_id:
        query = query.filter(Order.site_id == site_id)
    if keyword:
        query = query.filter(
            (Order.order_id.like(f"%{keyword}%")) |
            (Order.buyer_name.like(f"%{keyword}%"))
        )

    total = query.count()
    orders = query.order_by(desc(Order.order_date)).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": o.id,
                "order_id": o.order_id,
                "site_id": o.site_id,
                "status": o.status,
                "buyer_name": o.buyer_name,
                "total_amount": str(o.total_amount),
                "currency_id": o.currency_id,
                "shipping_cost": str(o.shipping_cost),
                "tracking_number": o.tracking_number,
                "order_date": _utc_iso(o.order_date),
                "payment_date": _utc_iso(o.payment_date),
                "order_date_source": o.order_date_source,
                "payment_date_source": o.payment_date_source,
            }
            for o in orders
        ],
    }


@router.get("/orders/{order_id}")
def get_order_detail(order_id: int, db: Session = Depends(get_db)):
    """订单详情"""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Order not found")

    items = db.query(OrderItem).filter(OrderItem.order_id == order_id).all()

    return {
        "id": order.id,
        "order_id": order.order_id,
        "site_id": order.site_id,
        "status": order.status,
        "buyer_name": order.buyer_name,
        "buyer_email": order.buyer_email,
        "buyer_phone": order.buyer_phone,
        "shipping_address": order.shipping_address,
        "shipping_city": order.shipping_city,
        "shipping_state": order.shipping_state,
        "shipping_zip_code": order.shipping_zip_code,
        "total_amount": str(order.total_amount),
        "currency_id": order.currency_id,
        "shipping_cost": str(order.shipping_cost),
        "commission_fee": str(order.commission_fee),
        "shipping_method": order.shipping_method,
        "tracking_number": order.tracking_number,
        "tracking_url": order.tracking_url,
        "order_date": _utc_iso(order.order_date),
        "payment_date": _utc_iso(order.payment_date),
        "order_date_source": order.order_date_source,
        "payment_date_source": order.payment_date_source,
        "shipping_date": _utc_iso(order.shipping_date),
        "items": [
            {
                "id": item.id,
                "item_id": item.item_id,
                "sku": item.sku,
                "title": item.title,
                "quantity": item.quantity,
                "unit_price": str(item.unit_price),
                "variation_name": item.variation_name,
                "image_url": item.image_url,
            }
            for item in items
        ],
    }


# ============ 库存管理 ============

@router.get("/inventory")
def list_inventory(
    warehouse_id: int = Query(None),
    keyword: str = Query(None),
    low_stock: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """库存列表"""
    query = db.query(Inventory)
    if warehouse_id:
        query = query.filter(Inventory.warehouse_id == warehouse_id)
    if keyword:
        query = query.filter(
            (Inventory.sku.like(f"%{keyword}%")) |
            (Inventory.product_name.like(f"%{keyword}%"))
        )
    if low_stock:
        query = query.filter(
            Inventory.quantity < Inventory.safe_stock,
            Inventory.safe_stock > 0,
        )

    total = query.count()
    items = query.order_by(desc(Inventory.updated_at)).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": i.id,
                "sku": i.sku,
                "product_name": i.product_name,
                "warehouse_id": i.warehouse_id,
                "quantity": i.quantity,
                "reserved_quantity": i.reserved_quantity,
                "available_quantity": i.quantity - i.reserved_quantity,
                "safe_stock": i.safe_stock,
                "avg_cost": str(i.avg_cost),
                "last_inbound_date": i.last_inbound_date.isoformat() if i.last_inbound_date else None,
                "is_low_stock": i.safe_stock > 0 and i.quantity < i.safe_stock,
            }
            for i in items
        ],
    }


@router.get("/inventory/movements")
def list_inventory_movements(
    sku: str = Query(None),
    warehouse_id: int = Query(None),
    movement_type: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """库存变动记录"""
    query = db.query(InventoryMovement)
    if sku:
        query = query.filter(InventoryMovement.sku == sku)
    if warehouse_id:
        query = query.filter(InventoryMovement.warehouse_id == warehouse_id)
    if movement_type:
        query = query.filter(InventoryMovement.movement_type == movement_type)

    total = query.count()
    items = query.order_by(desc(InventoryMovement.created_at)).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": m.id,
                "sku": m.sku,
                "warehouse_id": m.warehouse_id,
                "movement_type": m.movement_type,
                "quantity_change": m.quantity_change,
                "balance_after": m.balance_after,
                "reference_type": m.reference_type,
                "reference_id": m.reference_id,
                "remark": m.remark,
                "created_at": m.created_at.isoformat(),
            }
            for m in items
        ],
    }


# ============ 仓库管理 ============

@router.get("/warehouses")
def list_warehouses(db: Session = Depends(get_db)):
    """仓库列表"""
    warehouses = db.query(Warehouse).filter(Warehouse.is_active == 1).all()
    return [
        {
            "id": w.id,
            "name": w.name,
            "code": w.code,
            "address": w.address,
            "contact_name": w.contact_name,
            "contact_phone": w.contact_phone,
        }
        for w in warehouses
    ]


# ============ 采购管理 ============

@router.get("/purchase-orders")
def list_purchase_orders(
    status: str = Query(None),
    supplier_id: int = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """采购单列表"""
    query = db.query(PurchaseOrder)
    if status:
        query = query.filter(PurchaseOrder.status == status)
    if supplier_id:
        query = query.filter(PurchaseOrder.supplier_id == supplier_id)

    total = query.count()
    orders = query.order_by(desc(PurchaseOrder.created_at)).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": p.id,
                "po_number": p.po_number,
                "supplier_id": p.supplier_id,
                "warehouse_id": p.warehouse_id,
                "status": p.status,
                "total_cost": str(p.total_cost),
                "currency": p.currency,
                "expected_date": p.expected_date.isoformat() if p.expected_date else None,
                "created_at": p.created_at.isoformat(),
            }
            for p in orders
        ],
    }


@router.get("/suppliers")
def list_suppliers(db: Session = Depends(get_db)):
    """供应商列表"""
    suppliers = db.query(Supplier).filter(Supplier.is_active == 1).all()
    return [
        {
            "id": s.id,
            "name": s.name,
            "contact_name": s.contact_name,
            "contact_phone": s.contact_phone,
            "contact_qq": s.contact_qq,
        }
        for s in suppliers
    ]


# ============ 物流管理 ============

@router.get("/shipments")
def list_shipments(
    status: str = Query(None),
    keyword: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """物流单列表"""
    query = db.query(Shipment)
    if status:
        query = query.filter(Shipment.status == status)
    if keyword:
        query = query.filter(
            (Shipment.tracking_number.like(f"%{keyword}%")) |
            (Shipment.meli_order_id.like(f"%{keyword}%"))
        )

    total = query.count()
    items = query.order_by(desc(Shipment.updated_at)).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": s.id,
                "tracking_number": s.tracking_number,
                "meli_order_id": s.meli_order_id,
                "carrier": s.carrier,
                "shipping_method": s.shipping_method,
                "status": s.status,
                "destination": s.destination,
                "shipping_fee": str(s.shipping_fee),
                "latest_status_text": s.latest_status_text,
                "latest_status_time": s.latest_status_time.isoformat() if s.latest_status_time else None,
                "shipped_at": s.shipped_at.isoformat() if s.shipped_at else None,
                "delivered_at": s.delivered_at.isoformat() if s.delivered_at else None,
                "created_at": s.created_at.isoformat(),
            }
            for s in items
        ],
    }


# ============ 财务报表 ============

@router.get("/profit/summary")
def profit_summary(
    days: int = Query(30, ge=1, le=365),
    site_id: str = Query(None),
    db: Session = Depends(get_db),
):
    """利润汇总"""
    start_date = datetime.utcnow() - timedelta(days=days)

    query = db.query(
        func.count(ProfitRecord.id).label("orders_count"),
        func.sum(ProfitRecord.sales_amount).label("total_sales"),
        func.sum(ProfitRecord.product_cost).label("total_product_cost"),
        func.sum(ProfitRecord.shipping_cost).label("total_shipping_cost"),
        func.sum(ProfitRecord.platform_fee).label("total_platform_fee"),
        func.sum(ProfitRecord.gross_profit).label("total_gross_profit"),
        func.sum(ProfitRecord.net_profit).label("total_net_profit"),
    ).filter(ProfitRecord.date >= start_date)

    if site_id:
        query = query.filter(ProfitRecord.site_id == site_id)

    result = query.first()

    total_sales = result.total_sales or Decimal("0")
    total_net_profit = result.total_net_profit or Decimal("0")
    net_margin = (total_net_profit / total_sales * 100) if total_sales > 0 else Decimal("0")

    return {
        "orders_count": result.orders_count or 0,
        "total_sales": str(total_sales),
        "total_product_cost": str(result.total_product_cost or Decimal("0")),
        "total_shipping_cost": str(result.total_shipping_cost or Decimal("0")),
        "total_platform_fee": str(result.total_platform_fee or Decimal("0")),
        "total_gross_profit": str(result.total_gross_profit or Decimal("0")),
        "total_net_profit": str(total_net_profit),
        "net_margin": str(net_margin.quantize(Decimal("0.01"))),
        "currency": "MXN",
        "days": days,
    }


@router.get("/profit/daily")
def profit_daily(
    days: int = Query(30, ge=1, le=365),
    site_id: str = Query(None),
    db: Session = Depends(get_db),
):
    """每日利润趋势"""
    start_date = datetime.utcnow().date() - timedelta(days=days)

    query = db.query(
        func.date(ProfitRecord.date).label("date"),
        func.sum(ProfitRecord.sales_amount).label("sales"),
        func.sum(ProfitRecord.net_profit).label("profit"),
    ).filter(func.date(ProfitRecord.date) >= start_date)

    if site_id:
        query = query.filter(ProfitRecord.site_id == site_id)

    results = query.group_by(func.date(ProfitRecord.date)).order_by("date").all()

    return [
        {
            "date": str(r.date),
            "sales": str(r.sales or Decimal("0")),
            "profit": str(r.profit or Decimal("0")),
        }
        for r in results
    ]


@router.get("/profit/top-products")
def top_products_profit(
    days: int = Query(30, ge=1, le=365),
    site_id: str = Query(None),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """商品利润排行"""
    start_date = datetime.utcnow() - timedelta(days=days)

    query = db.query(
        ProfitRecord.sku,
        func.sum(ProfitRecord.quantity).label("qty"),
        func.sum(ProfitRecord.sales_amount).label("sales"),
        func.sum(ProfitRecord.net_profit).label("profit"),
    ).filter(ProfitRecord.date >= start_date)

    if site_id:
        query = query.filter(ProfitRecord.site_id == site_id)

    results = query.group_by(ProfitRecord.sku).order_by(desc("profit")).limit(limit).all()

    return [
        {
            "sku": r.sku,
            "quantity": r.qty or 0,
            "sales": str(r.sales or Decimal("0")),
            "profit": str(r.profit or Decimal("0")),
        }
        for r in results
    ]


# ============ 销售趋势 ============

@router.get("/sales/daily")
def sales_daily(
    days: int = Query(30, ge=1, le=365),
    site_id: str = Query(None),
    db: Session = Depends(get_db),
):
    """每日销售统计"""
    start_date = datetime.utcnow().date() - timedelta(days=days)

    query = db.query(
        func.date(DailySalesStat.date).label("date"),
        func.sum(DailySalesStat.orders_count).label("orders"),
        func.sum(DailySalesStat.sales_amount).label("sales"),
        func.sum(DailySalesStat.items_count).label("items"),
    ).filter(func.date(DailySalesStat.date) >= start_date)

    if site_id:
        query = query.filter(DailySalesStat.site_id == site_id)

    results = query.group_by(func.date(DailySalesStat.date)).order_by("date").all()

    return [
        {
            "date": str(r.date),
            "orders": r.orders or 0,
            "sales": str(r.sales or Decimal("0")),
            "items": r.items or 0,
        }
        for r in results
    ]


# ============ 同步 ============

@router.post("/sync/orders")
async def sync_orders(
    days: int = Query(30, ge=1, le=90),
    store_id: int = Query(None),
    db: Session = Depends(get_db),
):
    """手动触发订单同步"""
    from app.models.store import Store
    from app.services.meli.order_sync import sync_orders_for_store

    if store_id:
        store = db.query(Store).filter(Store.id == store_id, Store.oauth_status == "connected").first()
        if not store:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Store not found")
        result = await sync_orders_for_store(db, store, settings.token_encryption_key, days=days)
        return result
    else:
        # 同步所有店铺
        stores = db.query(Store).filter(Store.oauth_status == "connected").all()
        results = []
        for store in stores:
            r = await sync_orders_for_store(db, store, settings.token_encryption_key, days=days)
            results.append(r)
        return {"results": results, "count": len(results)}
