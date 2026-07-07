from fastapi import APIRouter
from pydantic import BaseModel

from app.schemas.drafts import ProductDraftCreate
from app.schemas.publishing import ListingChoice, PublishValidationResult
from app.schemas.reviews import ReviewResponse
from app.services.meli.publisher import validate_publish_request

router = APIRouter(prefix="/api/publishing", tags=["publishing"])


class PublishPreviewRequest(BaseModel):
    draft: ProductDraftCreate
    review: ReviewResponse
    listing_choice: ListingChoice
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
