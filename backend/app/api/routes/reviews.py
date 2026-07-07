from fastapi import APIRouter

from app.schemas.drafts import ProductDraftCreate
from app.schemas.reviews import ReviewResponse
from app.services.ai.review_policy import review_draft_locally

router = APIRouter(prefix="/api/reviews", tags=["reviews"])


@router.post("/local", response_model=ReviewResponse)
def review_local(draft: ProductDraftCreate) -> ReviewResponse:
    return review_draft_locally(draft)
