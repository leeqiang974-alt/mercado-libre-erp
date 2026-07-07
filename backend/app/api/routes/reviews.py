from fastapi import APIRouter

from app.core.config import get_settings
from app.schemas.drafts import ProductDraftCreate
from app.schemas.reviews import ReviewResponse
from app.services.ai.claude_client import ClaudeReviewClient
from app.services.ai.nvidia_client import NvidiaReviewClient
from app.services.ai.review_policy import review_draft_locally

router = APIRouter(prefix="/api/reviews", tags=["reviews"])
settings = get_settings()


@router.post("/local", response_model=ReviewResponse)
def review_local(draft: ProductDraftCreate) -> ReviewResponse:
    return review_draft_locally(draft)


@router.post("/claude", response_model=ReviewResponse)
async def review_claude(draft: ProductDraftCreate) -> ReviewResponse:
    return await ClaudeReviewClient(api_key=settings.claude_api_key).review_draft(draft)


@router.post("/nvidia", response_model=ReviewResponse)
async def review_nvidia(draft: ProductDraftCreate) -> ReviewResponse:
    return await NvidiaReviewClient(api_key=settings.nvidia_api_key).pre_screen_draft(draft)
