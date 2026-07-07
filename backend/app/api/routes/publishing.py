from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models.store import Store
from app.schemas.drafts import ProductDraftCreate
from app.schemas.publishing import (
    ListingChoice,
    PublishExecutionResult,
    PublishJobRead,
    PublishValidationResult,
)
from app.schemas.reviews import ReviewResponse
from app.services.draft_listing_configs import build_configured_draft
from app.services.meli.client import MercadoLibreClient
from app.services.meli.publisher import execute_publish, validate_publish_request
from app.services.meli.token_vault import resolve_store_access_token
from app.services.publish_jobs import create_publish_job, complete_publish_job, list_publish_jobs

router = APIRouter(prefix="/api/publishing", tags=["publishing"])
settings = get_settings()


class PublishPreviewRequest(BaseModel):
    draft: ProductDraftCreate
    review: ReviewResponse
    listing_choice: ListingChoice
    valid_listing_type_ids: list[str]
    human_approved: bool


class PublishExecuteRequest(PublishPreviewRequest):
    store_id: int
    product_draft_id: int | None = None


class PublishFromDraftPreviewRequest(BaseModel):
    product_draft_id: int
    review: ReviewResponse
    valid_listing_type_ids: list[str]
    human_approved: bool


@router.post("/preview", response_model=PublishValidationResult)
def publish_preview(payload: PublishPreviewRequest) -> PublishValidationResult:
    return validate_publish_request(
        draft=payload.draft,
        review=payload.review,
        listing_choice=payload.listing_choice,
        valid_listing_type_ids=payload.valid_listing_type_ids,
        human_approved=payload.human_approved,
    )


@router.post("/preview-from-draft", response_model=PublishValidationResult)
def publish_preview_from_draft(
    payload: PublishFromDraftPreviewRequest,
    db: Session = Depends(get_db),
) -> PublishValidationResult:
    draft, listing_choice = build_configured_draft(db, payload.product_draft_id)
    return validate_publish_request(
        draft=draft,
        review=payload.review,
        listing_choice=listing_choice,
        valid_listing_type_ids=payload.valid_listing_type_ids,
        human_approved=payload.human_approved,
    )


@router.post("/execute", response_model=PublishExecutionResult)
async def publish_execute(
    payload: PublishExecuteRequest, db: Session = Depends(get_db)
) -> PublishExecutionResult:
    store = db.get(Store, payload.store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found.")
    access_token = resolve_store_access_token(db, store, settings.token_encryption_key)
    if not access_token:
        return PublishExecutionResult(status="blocked", errors=["store_access_token_required"])
    job = create_publish_job(
        db=db,
        product_draft_id=payload.product_draft_id or 0,
        store_id=payload.store_id,
        requested_by="operator",
        draft=payload.draft,
        review=payload.review,
        listing_choice=payload.listing_choice,
    )
    result = await execute_publish(
        client=MercadoLibreClient(access_token=access_token),
        draft=payload.draft,
        review=payload.review,
        listing_choice=payload.listing_choice,
        valid_listing_type_ids=payload.valid_listing_type_ids,
        human_approved=payload.human_approved,
        allow_live_publish=settings.allow_live_publish,
    )
    complete_publish_job(db, job, result)
    return result.model_copy(update={"job_id": job.id})


@router.get("/jobs", response_model=list[PublishJobRead])
def get_publish_jobs(db: Session = Depends(get_db)) -> list[PublishJobRead]:
    return list_publish_jobs(db)
