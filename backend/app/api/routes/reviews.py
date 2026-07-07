from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.schemas.drafts import ProductDraftCreate
from app.schemas.reviews import ReviewResponse, ReviewResultRead
from app.services.ai.claude_client import ClaudeReviewClient
from app.services.ai.nvidia_client import NvidiaReviewClient
from app.services.ai.review_policy import review_draft_locally
from app.services.reviews import list_review_results, persist_review_result

router = APIRouter(prefix="/api/reviews", tags=["reviews"])
settings = get_settings()


@router.post("/local", response_model=ReviewResponse)
def review_local(
    draft: ProductDraftCreate,
    product_draft_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
) -> ReviewResponse:
    response = review_draft_locally(draft)
    return _persist_if_requested(db, response, product_draft_id)


@router.post("/claude", response_model=ReviewResponse)
async def review_claude(
    draft: ProductDraftCreate,
    product_draft_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
) -> ReviewResponse:
    response = await ClaudeReviewClient(api_key=settings.claude_api_key).review_draft(draft)
    return _persist_if_requested(db, response, product_draft_id)


@router.post("/nvidia", response_model=ReviewResponse)
async def review_nvidia(
    draft: ProductDraftCreate,
    product_draft_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
) -> ReviewResponse:
    response = await NvidiaReviewClient(api_key=settings.nvidia_api_key).pre_screen_draft(draft)
    return _persist_if_requested(db, response, product_draft_id)


@router.get("/drafts/{product_draft_id}", response_model=list[ReviewResultRead])
def review_history(product_draft_id: int, db: Session = Depends(get_db)) -> list[ReviewResultRead]:
    return list_review_results(db, product_draft_id)


def _persist_if_requested(
    db: Session,
    response: ReviewResponse,
    product_draft_id: int | None,
) -> ReviewResponse:
    if product_draft_id is None:
        return response
    result = persist_review_result(db, product_draft_id, response)
    return response.model_copy(update={"review_result_id": result.id})
