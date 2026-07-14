from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.schemas.drafts import ProductDraftCreate
from app.schemas.reviews import BehavioralAuditResponse, ReviewResponse, ReviewResultRead
from app.services.ai.claude_client import ClaudeReviewClient
from app.services.ai.nvidia_client import NvidiaReviewClient
from app.services.ai.review_policy import review_draft_locally
from app.services.audit_events import create_audit_event
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
    client = ClaudeReviewClient(api_key=settings.claude_api_key)
    response = await client.review_draft(draft)
    return _persist_if_requested(db, response, product_draft_id, model=getattr(client, "model", ""))


@router.post("/nvidia", response_model=ReviewResponse)
async def review_nvidia(
    draft: ProductDraftCreate,
    product_draft_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
) -> ReviewResponse:
    client = NvidiaReviewClient(api_key=settings.nvidia_api_key)
    response = await client.pre_screen_draft(draft)
    return _persist_if_requested(db, response, product_draft_id, model=getattr(client, "model", ""))


@router.post("/behavioral-audit", response_model=BehavioralAuditResponse)
async def behavioral_audit(
    draft: ProductDraftCreate,
    product_draft_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
) -> BehavioralAuditResponse:
    """Run NVIDIA pre-screening and Claude deep review before publish approval."""
    nvidia_client = NvidiaReviewClient(api_key=settings.nvidia_api_key)
    claude_client = ClaudeReviewClient(api_key=settings.claude_api_key)
    nvidia = await nvidia_client.pre_screen_draft(draft)
    claude = await claude_client.review_draft(draft)
    if product_draft_id is not None:
        nvidia = _persist_if_requested(
            db, nvidia, product_draft_id, model=getattr(nvidia_client, "model", "")
        )
        claude = _persist_if_requested(
            db, claude, product_draft_id, model=getattr(claude_client, "model", "")
        )

    aggregate = _aggregate_reviews(nvidia, claude)
    if product_draft_id is not None:
        create_audit_event(
            db=db,
            actor_type="ai_orchestrator",
            actor_id="claude+nvidia",
            action="review.behavioral_audit.completed",
            entity_type="product_draft",
            entity_id=str(product_draft_id),
            after={
                "decision": aggregate.decision,
                "risk_level": aggregate.risk_level,
                "providers": [nvidia.provider, claude.provider],
                "review_result_ids": [nvidia.review_result_id, claude.review_result_id],
            },
        )
    return BehavioralAuditResponse(nvidia=nvidia, claude=claude, aggregate=aggregate)


@router.get("/drafts/{product_draft_id}", response_model=list[ReviewResultRead])
def review_history(product_draft_id: int, db: Session = Depends(get_db)) -> list[ReviewResultRead]:
    return list_review_results(db, product_draft_id)


def _persist_if_requested(
    db: Session,
    response: ReviewResponse,
    product_draft_id: int | None,
    model: str = "",
) -> ReviewResponse:
    if product_draft_id is None:
        return response
    result = persist_review_result(db, product_draft_id, response, model=model)
    return response.model_copy(update={"review_result_id": result.id})


def _aggregate_reviews(*responses: ReviewResponse) -> ReviewResponse:
    decisions = [response.decision for response in responses]
    if "block" in decisions:
        decision = "block"
    elif "needs_human_review" in decisions:
        decision = "needs_human_review"
    else:
        decision = "pass"

    risk_levels = [response.risk_level for response in responses]
    if "high" in risk_levels:
        risk_level = "high"
    elif "medium" in risk_levels:
        risk_level = "medium"
    else:
        risk_level = "low"

    return ReviewResponse(
        provider="claude+nvidia_behavioral_audit",
        decision=decision,
        risk_level=risk_level,
        reason_codes=_unique_in_order(code for response in responses for code in response.reason_codes),
        reasons=_unique_in_order(reason for response in responses for reason in response.reasons),
        suggested_changes={
            provider: response.suggested_changes
            for provider, response in (("nvidia", responses[0]), ("claude", responses[1]))
        },
    )


def _unique_in_order(values):
    seen = set()
    result = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result
