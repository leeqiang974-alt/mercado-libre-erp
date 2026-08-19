import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.erp import (
    Order,
    OrderItem,
    Shipment,
    ProfitRecord,
    DailySalesStat,
)
from app.models.store import Store
from app.services.meli.client import MercadoLibreClient
from app.services.meli.token_vault import resolve_store_access_token


async def sync_orders_for_store(
    db: Session,
    store: Store,
    encryption_key: str,
    days: int = 30,
) -> dict:
    """同步美客多店铺的订单到 ERP 订单表"""
    access_token = resolve_store_access_token(db, store, encryption_key)
    if not access_token:
        raise ValueError(f"Store {store.id} has no valid access token")

    client = MercadoLibreClient(access_token=access_token)

    # 搜索最近 N 天的订单
    date_from = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    date_to = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    # CBT (全球卖家/跨境店) 用 marketplace API，本土站用 /orders/search
    if store.site_id.upper() == "CBT":
        path = (
            f"/marketplace/orders/search"
            f"?order.date_created.from={date_from}"
            f"&order.date_created.to={date_to}"
            f"&sort=date_desc"
            f"&limit=50"
        )
    else:
        # 本土站订单搜索 API
        path = (
            f"/orders/search"
            f"?seller={store.seller_id}"
            f"&order.date_created.from={date_from}"
            f"&order.date_created.to={date_to}"
            f"&sort=date_desc"
            f"&limit=50"
        )

    try:
        result = await client.get(path)
    except Exception as exc:
        return {"status": "error", "error": str(exc), "store_id": store.id}

    raw_results = result.get("results", []) if isinstance(result, dict) else []
    paging = result.get("paging", {}) if isinstance(result, dict) else {}
    total = paging.get("total", len(raw_results))

    # CBT marketplace API: 搜索接口只返回精简版，需要逐个获取订单详情
    # 本土站: 每个 result 就是完整的订单
    orders_list = []
    if store.site_id.upper() == "CBT":
        for group in raw_results:
            group_orders = group.get("orders", [])
            for ord in group_orders:
                order_id = str(ord.get("id", ""))
                if not order_id:
                    continue
                # 获取订单详情
                try:
                    detail = await client.get(f"/marketplace/orders/{order_id}")
                    # 合并 group 级别的 shipping
                    if "shipping" in group and detail.get("shipping") is None:
                        detail["shipping"] = group["shipping"]
                    orders_list.append(detail)
                except Exception:
                    # 如果获取详情失败，就用精简版
                    order_copy = dict(ord)
                    if "shipping" in group:
                        order_copy["shipping"] = group["shipping"]
                    orders_list.append(order_copy)
    else:
        orders_list = raw_results

    created = 0
    updated = 0
    item_detail_cache: dict[str, dict] = {}

    for order_data in orders_list:
        order_id_meli = str(order_data.get("id", ""))
        if not order_id_meli:
            continue

        existing = db.query(Order).filter(Order.order_id == order_id_meli).first()

        # 提取订单数据
        status = _map_order_status(order_data.get("status", ""))
        # CBT 用 paid_amount，本土站用 total_amount
        total_amount = Decimal(str(order_data.get("paid_amount", order_data.get("total_amount", 0))))
        currency_id = order_data.get("currency_id", store.site_id)
        order_date_source = order_data.get("date_created") or ""
        payment_date_source = order_data.get("date_closed") or order_date_source
        order_date = _parse_meli_datetime(order_date_source)
        payment_date = _parse_meli_datetime(payment_date_source)

        buyer = order_data.get("buyer", {})
        buyer_name = f"{buyer.get('first_name', '')} {buyer.get('last_name', '')}".strip()
        buyer_email = buyer.get("email", "")
        buyer_phone = ""
        buyer_phones = buyer.get("phone", {})
        if isinstance(buyer_phones, dict):
            area = buyer_phones.get("area_code", "")
            number = buyer_phones.get("number", "")
            if number:
                buyer_phone = f"{area}{number}"

        shipping = order_data.get("shipping", {})
        shipping_cost = Decimal(str(shipping.get("cost", 0))) if shipping else Decimal("0")
        shipping_method = shipping.get("shipping_method", "") if shipping else ""
        tracking_number = shipping.get("tracking_number", "") if shipping else ""

        # 收货地址
        ship_to = shipping.get("receiver_address", {}) if shipping else {}
        shipping_address = ""
        shipping_city = ""
        shipping_state = ""
        shipping_zip = ""
        shipping_country = ""
        if isinstance(ship_to, dict):
            shipping_address = ship_to.get("address_line", "") or ""
            city_obj = ship_to.get("city", {})
            if isinstance(city_obj, dict):
                shipping_city = city_obj.get("name", "") or ""
            state_obj = ship_to.get("state", {})
            if isinstance(state_obj, dict):
                shipping_state = state_obj.get("name", "") or ""
            shipping_zip = ship_to.get("zip_code", "") or ""
            country_obj = ship_to.get("country", {})
            if isinstance(country_obj, dict):
                shipping_country = country_obj.get("id", "") or ""

        if existing:
            existing.status = status
            existing.total_amount = total_amount
            existing.currency_id = currency_id
            existing.buyer_name = buyer_name
            existing.buyer_email = buyer_email
            existing.buyer_phone = buyer_phone
            existing.shipping_cost = shipping_cost
            existing.shipping_method = shipping_method
            existing.tracking_number = tracking_number
            existing.shipping_address = shipping_address
            existing.shipping_city = shipping_city
            existing.shipping_state = shipping_state
            existing.shipping_zip_code = shipping_zip
            existing.shipping_country = shipping_country
            existing.order_date = order_date or existing.order_date
            existing.payment_date = payment_date or existing.payment_date
            existing.order_date_source = order_date_source or existing.order_date_source
            existing.payment_date_source = payment_date_source or existing.payment_date_source
            existing.updated_at = datetime.utcnow()
            # 重同步时也刷新商品明细，避免旧订单一直没有商品和图片。
            db.query(OrderItem).filter(OrderItem.order_id == existing.id).delete(
                synchronize_session=False
            )
            await _sync_order_items(
                db,
                existing,
                order_data.get("order_items", []),
                currency_id,
                client,
                item_detail_cache,
            )
            updated += 1
        else:
            order_obj = Order(
                order_id=order_id_meli,
                site_id=store.site_id,
                store_id=store.id,
                status=status,
                buyer_name=buyer_name,
                buyer_email=buyer_email,
                buyer_phone=buyer_phone,
                shipping_address=shipping_address,
                shipping_city=shipping_city,
                shipping_state=shipping_state,
                shipping_zip_code=shipping_zip,
                shipping_country=shipping_country,
                total_amount=total_amount,
                currency_id=currency_id,
                shipping_cost=shipping_cost,
                commission_fee=Decimal("0"),  # 后续计算
                shipping_method=shipping_method,
                tracking_number=tracking_number if tracking_number else None,
                order_date=order_date,
                payment_date=payment_date,
                order_date_source=order_date_source or None,
                payment_date_source=payment_date_source or None,
            )
            db.add(order_obj)
            db.flush()
            created += 1

            await _sync_order_items(
                db,
                order_obj,
                order_data.get("order_items", []),
                currency_id,
                client,
                item_detail_cache,
            )

            # 同步物流单
            if tracking_number:
                _sync_shipment_for_order(db, order_obj, shipping)

    db.commit()

    return {
        "status": "success",
        "store_id": store.id,
        "seller_id": store.seller_id,
        "site_id": store.site_id,
        "total_available": total,
        "fetched": len(orders_list),
        "created": created,
        "updated": updated,
    }


def _parse_meli_datetime(value: str | None) -> datetime | None:
    """将 API 时间转为 UTC 无时区 datetime，原始值另行保存用于展示。"""
    if not value:
        return None
    try:
        normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
        parsed = datetime.fromisoformat(normalized)
        return (
            parsed.astimezone(timezone.utc).replace(tzinfo=None)
            if parsed.tzinfo
            else parsed
        )
    except (ValueError, AttributeError, TypeError):
        return None


def _sync_shipment_for_order(db: Session, order_obj: Order, shipping: dict) -> None:
    """为订单创建或更新物流单"""
    tracking = shipping.get("tracking_number", "") if shipping else ""
    if not tracking:
        return

    existing = db.query(Shipment).filter(Shipment.tracking_number == tracking).first()
    if existing:
        existing.status = _map_shipping_status(order_obj.status)
        existing.latest_status_time = datetime.utcnow()
        return

    carrier = shipping.get("shipping_mode", "") or ""
    status = _map_shipping_status(order_obj.status)
    destination = f"{order_obj.shipping_city}, {order_obj.shipping_state}"

    db.add(Shipment(
        tracking_number=tracking,
        order_id=order_obj.id,
        meli_order_id=order_obj.order_id,
        carrier=carrier,
        shipping_method=order_obj.shipping_method,
        status=status,
        destination=destination,
        shipping_fee=order_obj.shipping_cost,
        latest_status_text="物流已揽收",
        latest_status_time=datetime.utcnow(),
        shipped_at=order_obj.shipping_date,
    ))


async def _sync_order_items(
    db: Session,
    order_obj: Order,
    order_items: list,
    currency_id: str,
    client: MercadoLibreClient,
    item_detail_cache: dict[str, dict],
) -> None:
    """保存订单明细，并为 CBT 商品补齐跨境商品图片。"""
    for item_data in order_items or []:
        if not isinstance(item_data, dict):
            continue
        item_obj = item_data.get("item", {})
        if not isinstance(item_obj, dict):
            item_obj = {}

        item_id = str(item_obj.get("id", "") or "")
        item_detail = item_obj
        if item_id and item_id not in item_detail_cache:
            try:
                item_detail = await client.get(f"/marketplace/items/{item_id}")
            except Exception:
                item_detail = item_obj
            item_detail_cache[item_id] = item_detail
        elif item_id:
            item_detail = item_detail_cache[item_id]

        pictures = item_detail.get("pictures", []) if isinstance(item_detail, dict) else []
        image_url = ""
        if pictures and isinstance(pictures[0], dict):
            image_url = pictures[0].get("secure_url") or pictures[0].get("url") or ""
        image_url = image_url or str(item_detail.get("secure_thumbnail", "") or "")

        quantity = int(item_data.get("quantity", 1) or 1)
        unit_price = Decimal(str(item_data.get("unit_price", 0) or 0))
        seller_sku = item_detail.get("seller_sku", "")
        sku = str(seller_sku) if seller_sku else (
            f"ML-{item_id[:10]}" if item_id else f"ML-{order_obj.id}"
        )

        db.add(OrderItem(
            order_id=order_obj.id,
            item_id=item_id,
            sku=sku,
            title=str(item_detail.get("title", "") or ""),
            quantity=quantity,
            unit_price=unit_price,
            currency_id=currency_id,
            variation_id=str(item_detail.get("variation_id", "") or ""),
            variation_name=str(item_detail.get("variation_name", "") or ""),
            image_url=image_url or None,
        ))


def _map_order_status(meli_status: str) -> str:
    """美客多订单状态映射到 ERP 状态"""
    mapping = {
        "payment_required": "payment_required",
        "paid": "paid",
        "to_be_shipped": "packing",
        "shipped": "shipped",
        "delivered": "delivered",
        "cancelled": "cancelled",
        "canceled": "cancelled",
        "returned": "returned",
        "refunded": "refunded",
        "not_yet_paid": "payment_required",
        "payment_in_process": "payment_required",
    }
    return mapping.get(meli_status.lower(), meli_status.lower() if meli_status else "paid")


def _map_shipping_status(order_status: str) -> str:
    """根据订单状态映射物流状态"""
    if order_status in ("shipped", "delivered"):
        return "in_transit"
    if order_status == "delivered":
        return "delivered"
    if order_status in ("cancelled", "returned"):
        return "exception"
    return "pending"


async def sync_all_stores_orders(db: Session, encryption_key: str, days: int = 30) -> list[dict]:
    """同步所有已连接店铺的订单"""
    stores = db.query(Store).filter(Store.oauth_status == "connected").all()
    results = []
    for store in stores:
        result = await sync_orders_for_store(db, store, encryption_key, days=days)
        results.append(result)
    return results
