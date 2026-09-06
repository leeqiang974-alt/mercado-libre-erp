"""Bulk selection: batch product selection, draft creation, and item toggling."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models.collection_job import CollectionJob, CollectionJobStatus
from app.models.keyword_collection_campaign import KeywordCampaignStatus, KeywordCollectionCampaign
from app.models.product_draft import ProductDraft
from app.models.publish_job import PublishJob, PublishJobStatus
from app.models.source_product import SourceProduct
from app.models.store import Store
from app.schemas.drafts import ProductDraftCreate
from app.services.amazon.keyword_campaigns import normalize_keywords
from app.services.drafts import create_product_draft, normalize_listing_title
from app.services.meli.client import MercadoLibreClient
from app.services.meli.oauth import MercadoLibreOAuthClient
from app.services.meli.token_vault import resolve_fresh_store_access_token

router = APIRouter(prefix="/api/bulk-selection", tags=["bulk-selection"])

settings = get_settings()


def _first_image(sp: SourceProduct) -> str:
    images = sp.image_urls_json or []
    return str(images[0]) if images else ""


# ============ 1. 产品筛选 ============

@router.get("/products")
def list_bulk_products(
    min_price: float | None = Query(default=None, ge=0),
    max_price: float | None = Query(default=None, ge=0),
    keyword: str = Query(default="", max_length=200),
    has_measurements: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> dict:
    """筛选已采集的 Amazon 产品（价格带 + 关键词）。"""
    q = db.query(SourceProduct).filter(SourceProduct.source_price.is_not(None))
    if min_price is not None:
        q = q.filter(SourceProduct.source_price >= min_price)
    if max_price is not None:
        q = q.filter(SourceProduct.source_price <= max_price)
    kw = keyword.strip()
    if kw:
        like = f"%{kw}%"
        q = q.filter(or_(SourceProduct.title.ilike(like), SourceProduct.asin.ilike(kw)))
    total = q.count()
    rows = q.order_by(SourceProduct.source_price.asc()).offset(offset).limit(limit).all()
    products = []
    for sp in rows:
        measurements = sp.measurements_json or {}
        products.append({
            "id": sp.id,
            "asin": sp.asin,
            "title": sp.title,
            "source_price": sp.source_price,
            "source_currency": sp.source_currency,
            "image_url": _first_image(sp),
            "variant_count": len(sp.variants_json or []),
            "measurements": {
                "weight_kg": measurements.get("weight_kg") or measurements.get("weight") or None,
                "length_cm": measurements.get("length_cm") or None,
                "width_cm": measurements.get("width_cm") or None,
                "height_cm": measurements.get("height_cm") or None,
            },
            "collected_at": sp.collected_at.isoformat() if sp.collected_at else None,
        })
    return {"total": total, "products": products, "limit": limit, "offset": offset}


# ============ 2. 批量创建草稿 ============

@router.post("/drafts")
def bulk_create_drafts(
    payload: dict,
    db: Session = Depends(get_db),
) -> dict:
    """批量把选中产品生成草稿。

    payload: {
        "source_product_ids": [1,2,3],
        "target_site_id": "CBT",
        "target_category_id": "CBT95418",
        "price_mode": "multiplier" | "fixed",
        "price_value": 1.3 | 7.0,   # multiplier 或统一净收益
        "stock": 999,
    }
    """
    ids = payload.get("source_product_ids") or []
    if not ids:
        raise HTTPException(status_code=422, detail="source_product_ids_required")
    target_site_id = str(payload.get("target_site_id") or "CBT").upper()
    target_category_id = str(payload.get("target_category_id") or "")
    price_mode = str(payload.get("price_mode") or "multiplier")
    price_value = float(payload.get("price_value") or 1.3)
    stock = int(payload.get("stock") or 999)

    sources = db.query(SourceProduct).filter(SourceProduct.id.in_(ids)).all()
    if not sources:
        raise HTTPException(status_code=404, detail="no_source_products_found")

    created = []
    skipped = []
    for sp in sources:
        if not sp.source_price:
            skipped.append({"source_product_id": sp.id, "reason": "missing_price"})
            continue
        if sp.source_price <= 0:
            skipped.append({"source_product_id": sp.id, "reason": "invalid_price"})
            continue
        # 已有同源草稿则跳过
        existing = db.query(ProductDraft).filter(
            ProductDraft.source_product_id == sp.id,
            ProductDraft.target_site_id == target_site_id,
        ).first()
        if existing:
            skipped.append({"source_product_id": sp.id, "reason": "duplicate_draft", "draft_id": existing.id})
            continue

        price = sp.source_price * price_value if price_mode == "multiplier" else price_value
        try:
            draft = create_product_draft(
                db,
                ProductDraftCreate(
                    title=normalize_listing_title(sp.title, sp.brand),
                    description=sp.description or "",
                    brand=sp.brand,
                    target_site_id=target_site_id,
                    target_category_id=target_category_id,
                    condition="new",
                    source_price=sp.source_price,
                    source_currency=sp.source_currency or "USD",
                    price=round(price, 2),
                    currency="USD",
                    stock=stock,
                    listing_type_id="gold_special",
                    image_urls=list(sp.image_urls_json or []),
                ),
                source_product_id=sp.id,
            )
            created.append({"source_product_id": sp.id, "draft_id": draft.id, "title": draft.title})
        except Exception as exc:
            skipped.append({"source_product_id": sp.id, "reason": f"error:{str(exc)[:80]}"})

    return {"created": created, "skipped": skipped, "created_count": len(created), "skipped_count": len(skipped)}


# ============ 3. 批量上下架 ============

def _create_oauth_client(db: Session) -> MercadoLibreOAuthClient:
    return MercadoLibreOAuthClient(
        client_id=settings.meli_client_id,
        client_secret=settings.meli_client_secret,
        redirect_uri=settings.meli_redirect_uri,
    )


@router.post("/items/toggle")
async def bulk_toggle_items(
    payload: dict,
    db: Session = Depends(get_db),
) -> dict:
    """批量上下架已发布商品。

    payload: {"store_id": 3, "item_ids": ["CBT5173511210", ...], "action": "pause"|"activate"}
    """
    store_id = int(payload.get("store_id") or 0)
    item_ids = payload.get("item_ids") or []
    action = str(payload.get("action") or "pause").lower()
    if not item_ids:
        raise HTTPException(status_code=422, detail="item_ids_required")
    if action not in ("pause", "activate"):
        raise HTTPException(status_code=422, detail="action_must_be_pause_or_activate")
    store = db.get(Store, store_id)
    if store is None:
        raise HTTPException(status_code=404, detail="Store not found.")
    if store.oauth_status != "connected":
        raise HTTPException(status_code=409, detail="Store is not connected.")

    access_token = await resolve_fresh_store_access_token(
        db=db,
        store=store,
        encryption_key=settings.token_encryption_key,
        oauth_client=_create_oauth_client(db),
    )
    if not access_token:
        raise HTTPException(status_code=409, detail="Store access token is unavailable.")
    client = MercadoLibreClient(access_token=access_token, timeout=30)
    new_status = "paused" if action == "pause" else "active"

    results = []
    for item_id in item_ids:
        try:
            if store.site_id.strip().upper() == "CBT":
                resp = await client.put(f"/global/items/{item_id}", {"status": new_status})
            else:
                resp = await client.put(f"/items/{item_id}", {"status": new_status})
            # Meli returns 200 with empty body {} on successful status change
            ok = True
            detail = resp.get("status", "") if isinstance(resp, dict) else str(resp)
            results.append({"item_id": item_id, "success": ok, "detail": detail})
        except Exception as exc:
            results.append({"item_id": item_id, "success": False, "detail": str(exc)[:120]})

    return {"action": action, "results": results, "success_count": sum(1 for r in results if r["success"])}


# ============ 4. 批量选品战役 ============

@router.post("/campaigns")
def create_bulk_campaign(
    payload: dict,
    db: Session = Depends(get_db),
) -> dict:
    """创建批量选品战役：关键词组 + 价格带，后台持续发现并采集。

    payload: {
        "name": "浴室小件5-7美金",
        "keywords": ["shower squeegee", "soap dish drain"],
        "domain": "amazon.com",
        "target_site_id": "CBT",
        "min_price": 3.0, "max_price": 8.0,
        "pages_per_keyword": 1,
    }
    """
    name = str(payload.get("name") or "").strip()
    keywords = normalize_keywords(payload.get("keywords") or [])
    if not name:
        raise HTTPException(status_code=422, detail="name_required")
    if not keywords:
        raise HTTPException(status_code=422, detail="keywords_required")
    domain = str(payload.get("domain") or "amazon.com").strip().lower()
    target_site_id = str(payload.get("target_site_id") or "CBT").upper()
    min_price = payload.get("min_price")
    max_price = payload.get("max_price")
    pages = int(payload.get("pages_per_keyword") or 1)

    row = KeywordCollectionCampaign(
        name=name,
        domain=domain,
        target_site_id=target_site_id,
        keywords_json=keywords,
        pages_per_keyword=pages,
        status=KeywordCampaignStatus.PENDING.value,
        message="批量选品战役：等待后台按关键词发现商品。",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        "campaign_id": row.id,
        "name": row.name,
        "keywords": keywords,
        "status": row.status,
        "min_price": min_price,
        "max_price": max_price,
        "message": "战役已创建，后台将持续发现并采集商品。价格带筛选结果请在批量选品页查询。",
    }
