from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.product_draft import ProductDraft
from app.schemas.draft_approvals import DraftApprovalCreate, DraftApprovalRead
from app.schemas.draft_listing_config import DraftListingConfigRead, DraftListingConfigUpsert
from app.schemas.drafts import ProductDraftRead
from app.schemas.attribute_mapping import AttributeSuggestionRead
from app.schemas.pricing import DraftPricingRead, DraftPricingUpsert
from app.services.draft_approvals import approve_product_draft, to_approval_read
from app.services.draft_listing_configs import (
    get_draft_listing_config,
    to_listing_config_read,
    upsert_draft_listing_config,
)
from app.services.drafts import list_product_drafts
from app.services.draft_pricing import (
    get_draft_pricing,
    require_current_draft_pricing,
    to_pricing_read,
    upsert_draft_pricing,
)
from app.services.meli.attribute_mapping import suggest_draft_category_attributes

router = APIRouter(prefix="/api/drafts", tags=["drafts"])


@router.get("", response_model=list[ProductDraftRead])
def list_drafts(db: Session = Depends(get_db)) -> list[ProductDraftRead]:
    return list_product_drafts(db)


@router.put("/{product_draft_id}/pricing", response_model=DraftPricingRead)
def save_pricing(
    product_draft_id: int,
    payload: DraftPricingUpsert,
    db: Session = Depends(get_db),
) -> DraftPricingRead:
    return to_pricing_read(upsert_draft_pricing(db, product_draft_id, payload))


@router.get("/{product_draft_id}/pricing", response_model=DraftPricingRead | None)
def read_pricing(
    product_draft_id: int,
    optional: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> DraftPricingRead | None:
    try:
        pricing = get_draft_pricing(db, product_draft_id)
    except HTTPException as exc:
        if optional and exc.status_code == 404:
            return None
        raise
    draft = db.get(ProductDraft, product_draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Product draft not found.")
    require_current_draft_pricing(db, draft)
    return to_pricing_read(pricing)


@router.put("/{product_draft_id}/listing-config", response_model=DraftListingConfigRead)
def save_listing_config(
    product_draft_id: int,
    payload: DraftListingConfigUpsert,
    db: Session = Depends(get_db),
) -> DraftListingConfigRead:
    return to_listing_config_read(upsert_draft_listing_config(db, product_draft_id, payload))


@router.get("/{product_draft_id}/listing-config", response_model=DraftListingConfigRead | None)
def read_listing_config(
    product_draft_id: int,
    optional: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> DraftListingConfigRead | None:
    try:
        return to_listing_config_read(get_draft_listing_config(db, product_draft_id))
    except HTTPException as exc:
        if optional and exc.status_code == 404:
            return None
        raise


@router.get(
    "/{product_draft_id}/attribute-suggestions",
    response_model=AttributeSuggestionRead,
)
def read_attribute_suggestions(
    product_draft_id: int,
    category_id: str = Query(..., min_length=1, max_length=40),
    db: Session = Depends(get_db),
) -> AttributeSuggestionRead:
    return suggest_draft_category_attributes(db, product_draft_id, category_id)


@router.post("/{product_draft_id}/approval", response_model=DraftApprovalRead)
def approve_draft(
    product_draft_id: int,
    payload: DraftApprovalCreate,
    db: Session = Depends(get_db),
) -> DraftApprovalRead:
    return to_approval_read(approve_product_draft(db, product_draft_id, payload))
