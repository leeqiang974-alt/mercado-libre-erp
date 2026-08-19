from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.cbt_listing_config import CbtListingConfig
from app.models.draft_listing_config import DraftListingConfig
from app.models.product_draft import ProductDraft
from app.schemas.draft_category import DraftCategoryUpdate
from app.services.audit_events import create_audit_event
from app.services.drafts import to_draft_read, update_draft_content
from app.services.meli.metadata_cache import category_attributes_key, get_cached_metadata


def confirm_draft_category(
    db: Session, product_draft_id: int, payload: DraftCategoryUpdate
) -> tuple[ProductDraft, list[dict], bool]:
    draft = db.scalar(
        select(ProductDraft).where(ProductDraft.id == product_draft_id).with_for_update()
    )
    if draft is None:
        raise HTTPException(status_code=404, detail="Product draft not found.")
    site_id = payload.target_site_id.strip().upper()
    category_id = payload.category_id.strip().upper()
    if not category_id.startswith(site_id):
        raise HTTPException(status_code=422, detail="category_site_mismatch")
    if draft.content_version != payload.expected_content_version:
        raise HTTPException(status_code=409, detail="draft_content_version_conflict")
    if draft.target_category_id.strip().upper() == category_id and draft.target_site_id == site_id:
        metadata = get_cached_metadata(db, category_attributes_key(category_id)) or {}
        return draft, metadata.get("attributes", []) if metadata.get("verified") is True else [], metadata.get("verified") is True

    previous = {
        "target_site_id": draft.target_site_id,
        "target_category_id": draft.target_category_id,
        "content_version": draft.content_version,
    }
    db.query(DraftListingConfig).filter(DraftListingConfig.product_draft_id == product_draft_id).delete()
    db.query(CbtListingConfig).filter(CbtListingConfig.product_draft_id == product_draft_id).delete()
    update_draft_content(
        db,
        product_draft_id,
        expected_content_version=draft.content_version,
        target_site_id=site_id,
        target_category_id=category_id,
    )
    create_audit_event(
        db=db,
        actor_type="human",
        actor_id="operator",
        action="draft.category_confirmed",
        entity_type="product_draft",
        entity_id=str(product_draft_id),
        before=previous,
        after={"target_site_id": site_id, "target_category_id": category_id, "content_version": draft.content_version + 1},
        commit=False,
    )
    db.expire(draft)
    db.refresh(draft)
    metadata = get_cached_metadata(db, category_attributes_key(category_id)) or {}
    attributes_verified = metadata.get("verified") is True
    attributes = metadata.get("attributes", []) if attributes_verified else []
    db.commit()
    db.refresh(draft)
    return draft, attributes, attributes_verified


def to_category_read(draft: ProductDraft, attributes: list[dict], verified: bool) -> dict:
    return {
        "draft": to_draft_read(draft),
        "category_id": draft.target_category_id,
        "attributes_verified": verified,
        "attributes": attributes,
    }
