from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.draft_listing_config import DraftListingConfig
from app.models.product_draft import ProductDraft
from app.models.store import Store
from app.schemas.draft_listing_config import DraftListingConfigRead, DraftListingConfigUpsert
from app.schemas.drafts import ProductDraftCreate
from app.schemas.publishing import ListingChoice
from app.services.audit_events import create_audit_event
from app.services.drafts import update_draft_content
from app.services.draft_pricing import require_current_draft_pricing
from app.services.meli.category_validation import validate_category_attributes


def upsert_draft_listing_config(
    db: Session,
    product_draft_id: int,
    payload: DraftListingConfigUpsert,
) -> DraftListingConfig:
    draft = db.get(ProductDraft, product_draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Product draft not found.")
    if payload.store_id is not None:
        store = db.get(Store, payload.store_id)
        if store is None:
            raise HTTPException(status_code=404, detail="Store not found.")
        if store.oauth_status != "connected":
            raise HTTPException(status_code=409, detail="Store is not connected.")
        if store.site_id.strip().upper() != payload.site_id.strip().upper():
            raise HTTPException(status_code=422, detail="Store site does not match listing site.")
    category_errors = validate_category_attributes(
        db,
        payload.category_id,
        [attribute.model_dump(exclude_none=True) for attribute in payload.attributes],
        require_verified_metadata=True,
    )
    if category_errors:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_category_attributes", "errors": category_errors},
        )

    config = (
        db.query(DraftListingConfig)
        .populate_existing()
        .filter(DraftListingConfig.product_draft_id == product_draft_id)
        .one_or_none()
    )
    if config is None:
        config = DraftListingConfig(product_draft_id=product_draft_id)
        db.add(config)
        before = {}
    else:
        before = {
            "site_id": config.site_id,
            "store_id": config.store_id,
            "category_id": config.category_id,
            "listing_type_id": config.listing_type_id,
            "shipping_mode": config.shipping_mode,
            "shipping_logistic_type": config.shipping_logistic_type,
            "attributes": config.attributes_json or [],
        }

    config.site_id = payload.site_id
    config.store_id = payload.store_id
    config.category_id = payload.category_id
    config.listing_type_id = payload.listing_type_id
    config.fulfillment = payload.fulfillment
    config.shipping_mode = payload.shipping_mode
    config.shipping_logistic_type = payload.shipping_logistic_type
    config.attributes_json = [
        attribute.model_dump(exclude_none=True) for attribute in payload.attributes
    ]
    config.updated_at = datetime.now(UTC)

    update_draft_content(
        db,
        product_draft_id,
        target_site_id=payload.site_id,
        target_category_id=payload.category_id,
        listing_type_id=payload.listing_type_id,
    )
    create_audit_event(
        db,
        actor_type="human",
        actor_id="operator",
        action="draft_listing_config_updated",
        entity_type="product_draft",
        entity_id=str(product_draft_id),
        before=before,
        after={
            "site_id": config.site_id,
            "store_id": config.store_id,
            "category_id": config.category_id,
            "listing_type_id": config.listing_type_id,
            "fulfillment": config.fulfillment,
            "shipping_mode": config.shipping_mode,
            "shipping_logistic_type": config.shipping_logistic_type,
            "attributes": config.attributes_json or [],
        },
        commit=False,
    )
    db.commit()
    db.refresh(config)
    return config


def get_draft_listing_config(db: Session, product_draft_id: int) -> DraftListingConfig:
    config = (
        db.query(DraftListingConfig)
        .populate_existing()
        .filter(DraftListingConfig.product_draft_id == product_draft_id)
        .one_or_none()
    )
    if config is None:
        raise HTTPException(status_code=404, detail="Listing config not found.")
    return config


def build_configured_draft(
    db: Session, product_draft_id: int, *, lock_draft: bool = False
) -> tuple[ProductDraftCreate, ListingChoice]:
    statement = select(ProductDraft).where(ProductDraft.id == product_draft_id)
    if lock_draft:
        statement = statement.with_for_update().execution_options(populate_existing=True)
    draft = db.scalar(statement)
    if draft is None:
        raise HTTPException(status_code=404, detail="Product draft not found.")
    config = get_draft_listing_config(db, product_draft_id)
    require_current_draft_pricing(db, draft)
    category_errors = validate_category_attributes(
        db,
        config.category_id,
        config.attributes_json or [],
        require_verified_metadata=True,
    )
    if category_errors:
        raise HTTPException(
            status_code=409,
            detail={"code": "listing_config_stale", "errors": category_errors},
        )
    return (
        ProductDraftCreate(
            title=draft.title,
            description=draft.description,
            brand=draft.brand,
            target_site_id=config.site_id,
            target_category_id=config.category_id,
            condition=draft.condition,
            source_price=draft.source_price,
            source_currency=draft.source_currency,
            price=draft.price,
            currency=draft.currency,
            stock=draft.stock,
            listing_type_id=config.listing_type_id,
            image_urls=draft.image_urls_json or [],
            attributes=config.attributes_json or [],
        ),
        ListingChoice(
            site_id=config.site_id,
            store_id=config.store_id,
            listing_type_id=config.listing_type_id,
            fulfillment=config.fulfillment,
            shipping_mode=config.shipping_mode,
            shipping_logistic_type=config.shipping_logistic_type,
            attributes=config.attributes_json or [],
        ),
    )


def to_listing_config_read(config: DraftListingConfig) -> DraftListingConfigRead:
    return DraftListingConfigRead(
        id=config.id,
        product_draft_id=config.product_draft_id,
        site_id=config.site_id,
        store_id=config.store_id,
        category_id=config.category_id,
        listing_type_id=config.listing_type_id,
        fulfillment=config.fulfillment,
        shipping_mode=config.shipping_mode,
        shipping_logistic_type=config.shipping_logistic_type,
        attributes=config.attributes_json or [],
        created_at=config.created_at,
        updated_at=config.updated_at,
    )
