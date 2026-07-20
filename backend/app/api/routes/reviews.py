from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models.product_draft import ProductDraft
from app.schemas.drafts import ProductDraftCreate
from app.schemas.reviews import BehavioralAuditResponse, ReviewResponse, ReviewResultRead
from app.services.ai.claude_client import ClaudeReviewClient
from app.services.ai.nvidia_client import NvidiaReviewClient
from app.services.ai.provider_utils import AIProviderError
from app.services.ai.review_policy import review_draft_locally
from app.services.audit_events import create_audit_event
from app.services.draft_listing_configs import build_configured_draft
from app.services.reviews import list_review_results, persist_review_result, persist_review_results

router = APIRouter(prefix="/api/reviews", tags=["reviews"])
settings = get_settings()


@router.post("/local", response_model=ReviewResponse)
def review_local(
    draft: ProductDraftCreate,
    product_draft_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
) -> ReviewResponse:
    draft, draft_version = _canonical_review_draft(db, product_draft_id, draft)
    response = review_draft_locally(draft)
    return _persist_if_requested(db, response, product_draft_id, expected_draft_version=draft_version)


@router.post("/claude", response_model=ReviewResponse)
async def review_claude(
    draft: ProductDraftCreate,
    product_draft_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
) -> ReviewResponse:
    draft, draft_version = _canonical_review_draft(db, product_draft_id, draft)
    client = ClaudeReviewClient(api_key=settings.claude_api_key, model=settings.claude_model)
    try:
        response = await client.review_draft(draft)
    except AIProviderError as exc:
        raise _provider_http_error(exc) from exc
    return _persist_if_requested(
        db,
        response,
        product_draft_id,
        model=getattr(client, "model", ""),
        expected_draft_version=draft_version,
    )


@router.post("/nvidia", response_model=ReviewResponse)
async def review_nvidia(
    draft: ProductDraftCreate,
    product_draft_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
) -> ReviewResponse:
    draft, draft_version = _canonical_review_draft(db, product_draft_id, draft)
    client = NvidiaReviewClient(api_key=settings.nvidia_api_key, model=settings.nvidia_model)
    try:
        response = await client.pre_screen_draft(draft)
    except AIProviderError as exc:
        raise _provider_http_error(exc) from exc
    return _persist_if_requested(
        db,
        response,
        product_draft_id,
        model=getattr(client, "model", ""),
        expected_draft_version=draft_version,
    )


@router.post("/behavioral-audit", response_model=BehavioralAuditResponse)
async def behavioral_audit(
    draft: ProductDraftCreate,
    product_draft_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
) -> BehavioralAuditResponse:
    """Run NVIDIA pre-screening and Claude deep review before publish approval."""
    draft, draft_version = _canonical_review_draft(db, product_draft_id, draft)
    nvidia_client = NvidiaReviewClient(
        api_key=settings.nvidia_api_key, model=settings.nvidia_model
    )
    claude_client = ClaudeReviewClient(
        api_key=settings.claude_api_key, model=settings.claude_model
    )
    try:
        nvidia = await nvidia_client.pre_screen_draft(draft)
        claude = await claude_client.review_draft(draft)
    except AIProviderError as exc:
        raise _provider_http_error(exc) from exc
    aggregate = _aggregate_reviews(nvidia, claude)
    if product_draft_id is not None:
        results = persist_review_results(
            db,
            product_draft_id,
            [
                (nvidia, getattr(nvidia_client, "model", "")),
                (claude, getattr(claude_client, "model", "")),
                (
                    aggregate,
                    f"{getattr(nvidia_client, 'model', '')}+{getattr(claude_client, 'model', '')}",
                ),
            ],
            expected_draft_version=draft_version,
        )
        nvidia = nvidia.model_copy(update={"review_result_id": results[0].id})
        claude = claude.model_copy(update={"review_result_id": results[1].id})
        aggregate = aggregate.model_copy(update={"review_result_id": results[2].id})
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
                "review_result_ids": [
                    nvidia.review_result_id,
                    claude.review_result_id,
                    aggregate.review_result_id,
                ],
            },
        )
    return BehavioralAuditResponse(nvidia=nvidia, claude=claude, aggregate=aggregate)


def _canonical_review_draft(
    db: Session,
    product_draft_id: int | None,
    submitted: ProductDraftCreate,
) -> tuple[ProductDraftCreate, int | None]:
    if product_draft_id is None:
        return submitted, None
    model = db.scalar(
        select(ProductDraft)
        .where(ProductDraft.id == product_draft_id)
        .with_for_update()
    )
    if model is None:
        raise HTTPException(status_code=404, detail="Product draft not found.")
    try:
        draft, listing_choice = build_configured_draft(db, product_draft_id)
        canonical = draft.model_copy(update={"attributes": listing_choice.attributes})
    except HTTPException as exc:
        if exc.status_code != 404:
            raise
        canonical = ProductDraftCreate(
            title=model.title,
            description=model.description,
            brand=model.brand,
            target_site_id=model.target_site_id,
            target_category_id=model.target_category_id,
            condition=model.condition,
            source_price=model.source_price,
            source_currency=model.source_currency,
            price=model.price,
            currency=model.currency,
            stock=model.stock,
            listing_type_id=model.listing_type_id,
            image_urls=model.image_urls_json or [],
        )
    draft_version = model.content_version
    db.commit()
    return canonical, draft_version


@router.get("/drafts/{product_draft_id}", response_model=list[ReviewResultRead])
def review_history(product_draft_id: int, db: Session = Depends(get_db)) -> list[ReviewResultRead]:
    return list_review_results(db, product_draft_id)


def _persist_if_requested(
    db: Session,
    response: ReviewResponse,
    product_draft_id: int | None,
    model: str = "",
    expected_draft_version: int | None = None,
) -> ReviewResponse:
    if product_draft_id is None:
        return response
    result = persist_review_result(
        db,
        product_draft_id,
        response,
        model=model,
        expected_draft_version=expected_draft_version,
    )
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


def _provider_http_error(error: AIProviderError) -> HTTPException:
    return HTTPException(
        status_code=503,
        detail={"provider": error.provider, "code": error.code},
    )
