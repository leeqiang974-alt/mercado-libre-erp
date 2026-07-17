from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.draft_listing_config import DraftListingConfig
from app.models.product_draft import ProductDraft
from app.schemas.draft_listing_config import DraftListingConfigRead, DraftListingConfigUpsert
from app.schemas.drafts import ProductDraftCreate
from app.schemas.publishing import ListingChoice


def upsert_draft_listing_config(
    db: Session,
    product_draft_id: int,
    payload: DraftListingConfigUpsert,
) -> DraftListingConfig:
    draft = db.get(ProductDraft, product_draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Product draft not found.")

    config = (
        db.query(DraftListingConfig)
        .filter(DraftListingConfig.product_draft_id == product_draft_id)
        .one_or_none()
    )
    if config is None:
        config = DraftListingConfig(product_draft_id=product_draft_id)
        db.add(config)

    config.site_id = payload.site_id
    config.category_id = payload.category_id
    config.listing_type_id = payload.listing_type_id
    config.fulfillment = payload.fulfillment
    config.attributes_json = [attribute.model_dump() for attribute in payload.attributes]
    config.updated_at = datetime.now(UTC)

    draft.target_site_id = payload.site_id
    draft.target_category_id = payload.category_id
    draft.listing_type_id = payload.listing_type_id
    draft.content_version += 1
    draft.risk_status = "unreviewed"
    db.commit()
    db.refresh(config)
    return config


def get_draft_listing_config(db: Session, product_draft_id: int) -> DraftListingConfig:
    config = (
        db.query(DraftListingConfig)
        .filter(DraftListingConfig.product_draft_id == product_draft_id)
        .one_or_none()
    )
    if config is None:
        raise HTTPException(status_code=404, detail="Listing config not found.")
    return config


def build_configured_draft(db: Session, product_draft_id: int) -> tuple[ProductDraftCreate, ListingChoice]:
    draft = db.get(ProductDraft, product_draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Product draft not found.")
    config = get_draft_listing_config(db, product_draft_id)
    return (
        ProductDraftCreate(
            title=draft.title,
            description=draft.description,
            brand=draft.brand,
            target_site_id=config.site_id,
            target_category_id=config.category_id,
            condition=draft.condition,
            price=draft.price,
            currency=draft.currency,
            stock=draft.stock,
            listing_type_id=config.listing_type_id,
            image_urls=draft.image_urls_json or [],
            attributes=config.attributes_json or [],
        ),
        ListingChoice(
            site_id=config.site_id,
            listing_type_id=config.listing_type_id,
            fulfillment=config.fulfillment,
            attributes=config.attributes_json or [],
        ),
    )


def to_listing_config_read(config: DraftListingConfig) -> DraftListingConfigRead:
    return DraftListingConfigRead(
        id=config.id,
        product_draft_id=config.product_draft_id,
        site_id=config.site_id,
        category_id=config.category_id,
        listing_type_id=config.listing_type_id,
        fulfillment=config.fulfillment,
        attributes=config.attributes_json or [],
        created_at=config.created_at,
        updated_at=config.updated_at,
    )
