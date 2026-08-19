from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.cbt_listing_config import CbtListingConfig
from app.models.product_draft import ProductDraft
from app.models.store import Store
from app.schemas.cbt_listing_config import (
    CbtListingConfigRead,
    CbtListingConfigUpsert,
)
from app.services.audit_events import create_audit_event
from app.services.drafts import to_draft_read, update_draft_content
from app.services.source_products import source_variant_evidence_error


def upsert_cbt_listing_config(
    db: Session,
    product_draft_id: int,
    payload: CbtListingConfigUpsert,
) -> tuple[CbtListingConfig, object]:
    draft = db.scalar(
        select(ProductDraft).where(ProductDraft.id == product_draft_id).with_for_update()
    )
    if draft is None:
        raise HTTPException(status_code=404, detail="Product draft not found.")
    if source_error := source_variant_evidence_error(db, draft):
        raise HTTPException(status_code=409, detail={"code": "source_evidence_stale", "errors": [source_error]})
    store = db.get(Store, payload.store_id)
    if store is None:
        raise HTTPException(status_code=404, detail="Store not found.")
    if store.oauth_status != "connected" or store.site_id.strip().upper() != "CBT":
        raise HTTPException(status_code=422, detail="A connected CBT Global Selling store is required.")

    config = (
        db.query(CbtListingConfig)
        .populate_existing()
        .filter(CbtListingConfig.product_draft_id == product_draft_id)
        .one_or_none()
    )
    before = {} if config is None else _audit_snapshot(config)
    if config is None:
        config = CbtListingConfig(product_draft_id=product_draft_id, store_id=store.id)
        db.add(config)
    config.store_id = store.id
    config.category_id = payload.category_id
    config.family_name = payload.family_name
    config.global_title = payload.global_title
    config.description = payload.description
    config.price_usd = payload.price_usd
    config.available_quantity = payload.available_quantity
    config.attributes_json = [item.model_dump(exclude_none=True) for item in payload.attributes]
    config.sale_terms_json = [item.model_dump(exclude_none=True) for item in payload.sale_terms]
    config.sites_to_sell_json = [item.model_dump(exclude_none=True) for item in payload.sites_to_sell]
    config.updated_at = datetime.now(UTC)

    # The draft keeps the canonical source and review version. Persist CBT values
    # that affect publishing there so any existing approval/review is invalidated.
    update_draft_content(
        db,
        product_draft_id,
        target_site_id="CBT",
        target_category_id=payload.category_id,
        title=payload.global_title,
        description=payload.description,
        price=payload.price_usd,
        currency="USD",
        stock=payload.available_quantity,
    )
    db.refresh(draft)
    config.draft_content_version = draft.content_version
    create_audit_event(
        db=db,
        actor_type="human",
        actor_id="operator",
        action="cbt_listing_config_updated",
        entity_type="product_draft",
        entity_id=str(product_draft_id),
        before=before,
        after=_audit_snapshot(config),
        commit=False,
    )
    db.expire(draft)
    db.refresh(draft)
    draft_snapshot = to_draft_read(draft)
    db.commit()
    db.refresh(config)
    return config, draft_snapshot


def get_cbt_listing_config(db: Session, product_draft_id: int) -> CbtListingConfig:
    config = db.query(CbtListingConfig).filter(CbtListingConfig.product_draft_id == product_draft_id).one_or_none()
    if config is None:
        raise HTTPException(status_code=404, detail="CBT listing config not found.")
    return config


def to_cbt_listing_config_read(config: CbtListingConfig, draft: object) -> CbtListingConfigRead:
    return CbtListingConfigRead(
        id=config.id,
        product_draft_id=config.product_draft_id,
        store_id=config.store_id,
        category_id=config.category_id,
        family_name=config.family_name,
        global_title=config.global_title,
        description=config.description,
        price_usd=config.price_usd,
        available_quantity=config.available_quantity,
        attributes=config.attributes_json or [],
        sale_terms=config.sale_terms_json or [],
        sites_to_sell=config.sites_to_sell_json or [],
        draft_content_version=config.draft_content_version,
        draft=to_draft_read(draft),
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


def _audit_snapshot(config: CbtListingConfig) -> dict:
    return {
        "store_id": config.store_id,
        "category_id": config.category_id,
        "family_name": config.family_name,
        "global_title": config.global_title,
        "price_usd": config.price_usd,
        "available_quantity": config.available_quantity,
        "draft_content_version": config.draft_content_version,
        "attribute_ids": [item.get("id") for item in config.attributes_json or []],
        "marketplaces": [item.get("site_id") for item in config.sites_to_sell_json or []],
    }
