from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.draft_listing_config import DraftListingConfigRead, DraftListingConfigUpsert
from app.schemas.drafts import ProductDraftRead
from app.services.draft_listing_configs import (
    get_draft_listing_config,
    to_listing_config_read,
    upsert_draft_listing_config,
)
from app.services.drafts import list_product_drafts

router = APIRouter(prefix="/api/drafts", tags=["drafts"])


@router.get("", response_model=list[ProductDraftRead])
def list_drafts(db: Session = Depends(get_db)) -> list[ProductDraftRead]:
    return list_product_drafts(db)


@router.put("/{product_draft_id}/listing-config", response_model=DraftListingConfigRead)
def save_listing_config(
    product_draft_id: int,
    payload: DraftListingConfigUpsert,
    db: Session = Depends(get_db),
) -> DraftListingConfigRead:
    return to_listing_config_read(upsert_draft_listing_config(db, product_draft_id, payload))


@router.get("/{product_draft_id}/listing-config", response_model=DraftListingConfigRead)
def read_listing_config(
    product_draft_id: int,
    db: Session = Depends(get_db),
) -> DraftListingConfigRead:
    return to_listing_config_read(get_draft_listing_config(db, product_draft_id))
