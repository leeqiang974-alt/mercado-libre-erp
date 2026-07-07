from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import get_settings
from app.schemas.drafts import ProductDraftCreate
from app.schemas.publishing import ListingChoice, PublishExecutionResult, PublishValidationResult
from app.schemas.reviews import ReviewResponse
from app.services.meli.client import MercadoLibreClient
from app.services.meli.publisher import execute_publish, validate_publish_request

router = APIRouter(prefix="/api/publishing", tags=["publishing"])
settings = get_settings()


class PublishPreviewRequest(BaseModel):
    draft: ProductDraftCreate
    review: ReviewResponse
    listing_choice: ListingChoice
    valid_listing_type_ids: list[str]
    human_approved: bool


class PublishExecuteRequest(PublishPreviewRequest):
    access_token: str


@router.post("/preview", response_model=PublishValidationResult)
def publish_preview(payload: PublishPreviewRequest) -> PublishValidationResult:
    return validate_publish_request(
        draft=payload.draft,
        review=payload.review,
        listing_choice=payload.listing_choice,
        valid_listing_type_ids=payload.valid_listing_type_ids,
        human_approved=payload.human_approved,
    )


@router.post("/execute", response_model=PublishExecutionResult)
async def publish_execute(payload: PublishExecuteRequest) -> PublishExecutionResult:
    return await execute_publish(
        client=MercadoLibreClient(access_token=payload.access_token),
        draft=payload.draft,
        review=payload.review,
        listing_choice=payload.listing_choice,
        valid_listing_type_ids=payload.valid_listing_type_ids,
        human_approved=payload.human_approved,
        allow_live_publish=settings.allow_live_publish,
    )
