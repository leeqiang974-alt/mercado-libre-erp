from time import perf_counter

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
from app.services.draft_pricing import require_current_draft_pricing
from app.services.integration_credentials import resolve_integration_credentials
from app.services.reviews import (
    ReviewBatchAudit,
    ReviewExecution,
    list_review_results,
    persist_review_result,
    persist_review_results,
    persist_stale_review_result,
)

router = APIRouter(prefix="/api/reviews", tags=["reviews"])
settings = get_settings()


@router.post("/local", response_model=ReviewResponse)
def review_local(
    draft: ProductDraftCreate,
    product_draft_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
) -> ReviewResponse:
    draft, draft_version = _canonical_review_draft(db, product_draft_id, draft)
    started = perf_counter()
    response = review_draft_locally(draft)
    return _persist_if_requested(
        db,
        response,
        product_draft_id,
        model="local-policy",
        prompt_version="local-policy-v1",
        duration_ms=_elapsed_ms(started),
        expected_draft_version=draft_version,
    )


@router.post("/claude", response_model=ReviewResponse)
async def review_claude(
    draft: ProductDraftCreate,
    product_draft_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
) -> ReviewResponse:
    draft, draft_version = _canonical_review_draft(db, product_draft_id, draft)
    credentials = resolve_integration_credentials(db, settings)
    client = ClaudeReviewClient(api_key=credentials.claude_api_key, model=settings.claude_model)
    started = perf_counter()
    try:
        response = await client.review_draft(draft)
    except AIProviderError as exc:
        _audit_provider_failure(
            db, product_draft_id, exc, client, _elapsed_ms(started)
        )
        raise _provider_http_error(exc) from exc
    return _persist_provider_if_requested(
        db,
        response,
        product_draft_id,
        model=getattr(client, "model", ""),
        prompt_version=getattr(client, "prompt_version", ""),
        duration_ms=_elapsed_ms(started),
        expected_draft_version=draft_version,
    )


@router.post("/nvidia", response_model=ReviewResponse)
async def review_nvidia(
    draft: ProductDraftCreate,
    product_draft_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
) -> ReviewResponse:
    draft, draft_version = _canonical_review_draft(db, product_draft_id, draft)
    credentials = resolve_integration_credentials(db, settings)
    client = NvidiaReviewClient(api_key=credentials.nvidia_api_key, model=settings.nvidia_model)
    started = perf_counter()
    try:
        response = await client.pre_screen_draft(draft)
    except AIProviderError as exc:
        _audit_provider_failure(
            db, product_draft_id, exc, client, _elapsed_ms(started)
        )
        raise _provider_http_error(exc) from exc
    return _persist_provider_if_requested(
        db,
        response,
        product_draft_id,
        model=getattr(client, "model", ""),
        prompt_version=getattr(client, "prompt_version", ""),
        duration_ms=_elapsed_ms(started),
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
    credentials = resolve_integration_credentials(db, settings)
    nvidia_client = NvidiaReviewClient(
        api_key=credentials.nvidia_api_key, model=settings.nvidia_model
    )
    claude_client = ClaudeReviewClient(
        api_key=credentials.claude_api_key, model=settings.claude_model
    )
    nvidia_started = perf_counter()
    try:
        nvidia = await nvidia_client.pre_screen_draft(draft)
    except AIProviderError as exc:
        _audit_provider_failure(
            db, product_draft_id, exc, nvidia_client, _elapsed_ms(nvidia_started)
        )
        raise _provider_http_error(exc) from exc
    nvidia_duration_ms = _elapsed_ms(nvidia_started)
    nvidia = _persist_provider_if_requested(
        db,
        nvidia,
        product_draft_id,
        model=getattr(nvidia_client, "model", ""),
        prompt_version=getattr(nvidia_client, "prompt_version", ""),
        duration_ms=nvidia_duration_ms,
        expected_draft_version=draft_version,
    )

    claude_started = perf_counter()
    try:
        claude = await claude_client.review_draft(draft)
    except AIProviderError as exc:
        _audit_provider_failure(
            db, product_draft_id, exc, claude_client, _elapsed_ms(claude_started)
        )
        raise _provider_http_error(exc) from exc
    claude_duration_ms = _elapsed_ms(claude_started)
    claude = _persist_provider_if_requested(
        db,
        claude,
        product_draft_id,
        model=getattr(claude_client, "model", ""),
        prompt_version=getattr(claude_client, "prompt_version", ""),
        duration_ms=claude_duration_ms,
        expected_draft_version=draft_version,
    )
    aggregate = _aggregate_reviews(nvidia, claude)
    if product_draft_id is not None:
        results = persist_review_results(
            db,
            product_draft_id,
            [
                ReviewExecution(
                    aggregate,
                    model=(
                        f"{getattr(nvidia_client, 'model', '')}+"
                        f"{getattr(claude_client, 'model', '')}"
                    ),
                    prompt_version=(
                        f"{getattr(nvidia_client, 'prompt_version', '')}+"
                        f"{getattr(claude_client, 'prompt_version', '')}"
                    ),
                    duration_ms=nvidia_duration_ms + claude_duration_ms,
                ),
            ],
            expected_draft_version=draft_version,
            batch_audit=ReviewBatchAudit(
                actor_type="ai_orchestrator",
                actor_id="claude+nvidia",
                action="review.behavioral_audit.completed",
                after={
                    "decision": aggregate.decision,
                    "risk_level": aggregate.risk_level,
                    "providers": [nvidia.provider, claude.provider],
                    "models": [
                        getattr(nvidia_client, "model", ""),
                        getattr(claude_client, "model", ""),
                    ],
                    "prompt_versions": [
                        getattr(nvidia_client, "prompt_version", ""),
                        getattr(claude_client, "prompt_version", ""),
                    ],
                    "duration_ms": nvidia_duration_ms + claude_duration_ms,
                    "provider_review_result_ids": [
                        nvidia.review_result_id,
                        claude.review_result_id,
                    ],
                },
            ),
        )
        aggregate = aggregate.model_copy(update={"review_result_id": results[0].id})
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
    require_current_draft_pricing(db, model)
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
    prompt_version: str = "",
    duration_ms: int = 0,
    expected_draft_version: int | None = None,
) -> ReviewResponse:
    if product_draft_id is None:
        return response
    result = persist_review_result(
        db,
        product_draft_id,
        response,
        model=model,
        prompt_version=prompt_version,
        duration_ms=duration_ms,
        expected_draft_version=expected_draft_version,
    )
    return response.model_copy(update={"review_result_id": result.id})


def _persist_provider_if_requested(
    db: Session,
    response: ReviewResponse,
    product_draft_id: int | None,
    model: str = "",
    prompt_version: str = "",
    duration_ms: int = 0,
    expected_draft_version: int | None = None,
) -> ReviewResponse:
    try:
        return _persist_if_requested(
            db,
            response,
            product_draft_id,
            model=model,
            prompt_version=prompt_version,
            duration_ms=duration_ms,
            expected_draft_version=expected_draft_version,
        )
    except HTTPException as exc:
        if (
            product_draft_id is None
            or expected_draft_version is None
            or exc.status_code != 409
            or exc.detail != "draft_content_version_changed_during_review"
        ):
            raise
        persist_stale_review_result(
            db,
            product_draft_id,
            response,
            model=model,
            prompt_version=prompt_version,
            duration_ms=duration_ms,
            draft_version=expected_draft_version,
        )
        raise


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
        input_tokens=_sum_optional(response.input_tokens for response in responses),
        output_tokens=_sum_optional(response.output_tokens for response in responses),
        total_tokens=_sum_optional(response.total_tokens for response in responses),
    )


def _unique_in_order(values):
    seen = set()
    result = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _sum_optional(values) -> int | None:
    items = list(values)
    if not items or any(value is None for value in items):
        return None
    return sum(items)


def _provider_http_error(error: AIProviderError) -> HTTPException:
    if error.code == "rate_limited":
        status_code = 429
    elif error.code in {
        "api_key_required",
        "provider_unreachable",
        "provider_unavailable",
        "request_failed",
    }:
        status_code = 503
    else:
        status_code = 502
    return HTTPException(
        status_code=status_code,
        detail={
            "provider": error.provider,
            "code": error.code,
            "retryable": error.retryable,
            "retry_after_seconds": error.retry_after_seconds,
            "request_id": error.request_id,
            "provider_http_status": error.http_status,
        },
    )


def _elapsed_ms(started: float) -> int:
    return max(0, round((perf_counter() - started) * 1000))


def _audit_provider_failure(
    db: Session,
    product_draft_id: int | None,
    error: AIProviderError,
    client,
    duration_ms: int,
) -> None:
    if product_draft_id is None:
        return
    create_audit_event(
        db=db,
        actor_type="ai_provider",
        actor_id=error.provider,
        action="review.failed",
        entity_type="product_draft",
        entity_id=str(product_draft_id),
        after={
            "provider_status": "failed",
            "error_code": error.code,
            "model": getattr(client, "model", ""),
            "prompt_version": getattr(client, "prompt_version", ""),
            "duration_ms": duration_ms,
            "http_status": error.http_status,
            "retryable": error.retryable,
            "retry_after_seconds": error.retry_after_seconds,
            "provider_request_id": error.request_id,
        },
    )
