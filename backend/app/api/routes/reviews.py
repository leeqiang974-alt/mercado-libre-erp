from datetime import UTC, datetime, timedelta
from time import perf_counter

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models.product_draft import ProductDraft
from app.models.review_job import ReviewJob, ReviewJobStatus
from app.models.review_result import ReviewResult
from app.schemas.drafts import ProductDraftCreate
from app.schemas.reviews import (
    BehavioralAuditResponse,
    DraftReviewSubject,
    ReviewListingContext,
    ReviewPricingContext,
    ReviewResponse,
    ReviewResultRead,
    ReviewJobBatchCreate,
    ReviewJobBatchResponse,
    ReviewJobRead,
)
from app.services.ai.claude_client import ClaudeReviewClient
from app.services.ai.nvidia_client import NvidiaReviewClient
from app.services.ai.provider_utils import AIProviderError, BEHAVIORAL_AUDIT_PROMPT_VERSION
from app.services.ai.review_policy import review_draft_locally
from app.services.audit_events import create_audit_event
from app.services.draft_listing_configs import (
    build_configured_draft,
    get_draft_listing_config,
)
from app.services.draft_pricing import get_draft_pricing, require_current_draft_pricing
from app.services.integration_credentials import resolve_integration_credentials
from app.services.provider_pricing import (
    active_provider_model_price_id,
    estimate_review_cost,
)
from app.services.reviews import (
    ReviewBatchAudit,
    ReviewExecution,
    get_latest_behavioral_review,
    list_review_results,
    persist_review_result,
    persist_review_results,
    persist_stale_review_result,
    provider_review_context_errors,
    to_review_result_read,
)
from app.services.review_jobs import (
    audit_review_job_finished,
    complete_review_job,
    enqueue_review_batch,
    list_review_jobs,
    start_synchronous_review_job,
)

router = APIRouter(prefix="/api/reviews", tags=["reviews"])
settings = get_settings()


@router.post("/jobs/batch", response_model=ReviewJobBatchResponse)
def enqueue_behavioral_audit_batch(
    payload: ReviewJobBatchCreate,
    db: Session = Depends(get_db),
) -> ReviewJobBatchResponse:
    credentials = resolve_integration_credentials(db, settings)
    missing = [
        provider
        for provider, configured in (
            ("claude", bool(credentials.claude_api_key)),
            ("nvidia", bool(credentials.nvidia_api_key)),
        )
        if not configured
    ]
    if missing:
        raise HTTPException(
            status_code=409,
            detail={"code": "review_providers_not_configured", "providers": missing},
        )
    return enqueue_review_batch(db, payload.draft_ids)


@router.get("/jobs", response_model=list[ReviewJobRead])
def review_jobs(
    limit: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[ReviewJobRead]:
    return list_review_jobs(db, limit=limit)


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
    acknowledge_provider_costs: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> ReviewResponse:
    review_job = start_synchronous_review_job(
        db,
        product_draft_id,
        acknowledge_provider_costs=acknowledge_provider_costs,
    )
    draft_version, review_subject, client, price_config_id = (
        _prepare_synchronous_provider_review(
            db,
            review_job,
            product_draft_id,
            draft,
            provider="claude",
        )
    )
    started = perf_counter()
    try:
        response = await client.review_draft(review_subject)
    except AIProviderError as exc:
        _audit_provider_failure(
            db, product_draft_id, exc, client, _elapsed_ms(started)
        )
        error = _provider_http_error(exc)
        _finish_synchronous_review_job(db, review_job, error=error)
        raise error from exc
    except Exception:
        _finish_unexpected_synchronous_review_job(db, review_job)
        raise
    try:
        result = _persist_provider_if_requested(
            db,
            response,
            product_draft_id,
            model=getattr(client, "model", ""),
            prompt_version=getattr(client, "prompt_version", ""),
            duration_ms=_elapsed_ms(started),
            expected_draft_version=draft_version,
            price_config_id=price_config_id,
            price_config_captured=True,
            review_job_id=review_job.id if review_job else None,
        )
    except HTTPException as exc:
        _finish_synchronous_review_job(db, review_job, error=exc)
        raise
    except Exception:
        _finish_unexpected_synchronous_review_job(db, review_job)
        raise
    _finish_synchronous_review_job(
        db, review_job, aggregate_review_result_id=result.review_result_id
    )
    return result


@router.post("/nvidia", response_model=ReviewResponse)
async def review_nvidia(
    draft: ProductDraftCreate,
    product_draft_id: int | None = Query(default=None),
    acknowledge_provider_costs: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> ReviewResponse:
    review_job = start_synchronous_review_job(
        db,
        product_draft_id,
        acknowledge_provider_costs=acknowledge_provider_costs,
    )
    draft_version, review_subject, client, price_config_id = (
        _prepare_synchronous_provider_review(
            db,
            review_job,
            product_draft_id,
            draft,
            provider="nvidia",
        )
    )
    started = perf_counter()
    try:
        response = await client.pre_screen_draft(review_subject)
    except AIProviderError as exc:
        _audit_provider_failure(
            db, product_draft_id, exc, client, _elapsed_ms(started)
        )
        error = _provider_http_error(exc)
        _finish_synchronous_review_job(db, review_job, error=error)
        raise error from exc
    except Exception:
        _finish_unexpected_synchronous_review_job(db, review_job)
        raise
    try:
        result = _persist_provider_if_requested(
            db,
            response,
            product_draft_id,
            model=getattr(client, "model", ""),
            prompt_version=getattr(client, "prompt_version", ""),
            duration_ms=_elapsed_ms(started),
            expected_draft_version=draft_version,
            price_config_id=price_config_id,
            price_config_captured=True,
            review_job_id=review_job.id if review_job else None,
        )
    except HTTPException as exc:
        _finish_synchronous_review_job(db, review_job, error=exc)
        raise
    except Exception:
        _finish_unexpected_synchronous_review_job(db, review_job)
        raise
    _finish_synchronous_review_job(
        db, review_job, aggregate_review_result_id=result.review_result_id
    )
    return result


@router.post("/behavioral-audit", response_model=BehavioralAuditResponse)
async def behavioral_audit(
    draft: ProductDraftCreate,
    product_draft_id: int | None = Query(default=None),
    acknowledge_provider_costs: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> BehavioralAuditResponse:
    """Run NVIDIA pre-screening and Claude deep review before publish approval."""
    review_job = start_synchronous_review_job(
        db,
        product_draft_id,
        acknowledge_provider_costs=acknowledge_provider_costs,
    )
    try:
        result = await _run_behavioral_audit(
            draft,
            product_draft_id,
            db,
            review_job_id=review_job.id if review_job else None,
        )
    except HTTPException as exc:
        _finish_synchronous_review_job(db, review_job, error=exc)
        raise
    except Exception:
        _finish_unexpected_synchronous_review_job(db, review_job)
        raise
    _finish_synchronous_review_job(
        db,
        review_job,
        aggregate_review_result_id=result.aggregate.review_result_id,
    )
    return result


async def run_behavioral_audit_for_draft(
    db: Session, product_draft_id: int, review_job_id: int
) -> BehavioralAuditResponse:
    return await _run_behavioral_audit(
        ProductDraftCreate(title=""),
        product_draft_id,
        db,
        review_job_id=review_job_id,
    )


async def _run_behavioral_audit(
    draft: ProductDraftCreate,
    product_draft_id: int | None,
    db: Session,
    *,
    review_job_id: int | None = None,
) -> BehavioralAuditResponse:
    draft, draft_version, review_subject = _canonical_provider_review_subject(
        db, product_draft_id, draft
    )
    credentials = resolve_integration_credentials(db, settings)
    nvidia_client = NvidiaReviewClient(
        api_key=credentials.nvidia_api_key, model=settings.nvidia_model
    )
    claude_client = ClaudeReviewClient(
        api_key=credentials.claude_api_key, model=settings.claude_model
    )
    nvidia_price_config_id = active_provider_model_price_id(
        db, provider="nvidia", model=getattr(nvidia_client, "model", "")
    )
    claude_price_config_id = active_provider_model_price_id(
        db, provider="claude", model=getattr(claude_client, "model", "")
    )
    db.commit()
    nvidia = _reusable_job_provider_result(
        db,
        review_job_id=review_job_id,
        provider="nvidia",
        model=getattr(nvidia_client, "model", ""),
        prompt_version=getattr(nvidia_client, "prompt_version", ""),
        draft_version=draft_version,
    )
    nvidia_duration_ms = 0
    if nvidia is None:
        nvidia_started = perf_counter()
        try:
            nvidia = await nvidia_client.pre_screen_draft(review_subject)
        except AIProviderError as exc:
            _audit_provider_failure(
                db,
                product_draft_id,
                exc,
                nvidia_client,
                _elapsed_ms(nvidia_started),
                review_job_id=review_job_id,
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
            price_config_id=nvidia_price_config_id,
            price_config_captured=True,
            review_job_id=review_job_id,
        )

    claude = _reusable_job_provider_result(
        db,
        review_job_id=review_job_id,
        provider="claude",
        model=getattr(claude_client, "model", ""),
        prompt_version=getattr(claude_client, "prompt_version", ""),
        draft_version=draft_version,
    )
    claude_duration_ms = 0
    if claude is None:
        claude_started = perf_counter()
        try:
            claude = await claude_client.review_draft(review_subject)
        except AIProviderError as exc:
            _audit_provider_failure(
                db,
                product_draft_id,
                exc,
                claude_client,
                _elapsed_ms(claude_started),
                review_job_id=review_job_id,
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
            price_config_id=claude_price_config_id,
            price_config_captured=True,
            review_job_id=review_job_id,
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
                    prompt_version=BEHAVIORAL_AUDIT_PROMPT_VERSION,
                    duration_ms=nvidia_duration_ms + claude_duration_ms,
                    review_job_id=review_job_id,
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
    *,
    commit: bool = True,
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
    if commit:
        db.commit()
    return canonical, draft_version


def _canonical_provider_review_subject(
    db: Session,
    product_draft_id: int | None,
    submitted: ProductDraftCreate,
) -> tuple[ProductDraftCreate, int | None, DraftReviewSubject]:
    draft, draft_version = _canonical_review_draft(
        db,
        product_draft_id,
        submitted,
        commit=False,
    )
    subject = _provider_review_subject(db, product_draft_id, draft)
    db.commit()
    return draft, draft_version, subject


def _prepare_synchronous_provider_review(
    db: Session,
    review_job: ReviewJob | None,
    product_draft_id: int | None,
    submitted: ProductDraftCreate,
    *,
    provider: str,
) -> tuple[int | None, DraftReviewSubject, object, int | None]:
    try:
        _, draft_version, review_subject = _canonical_provider_review_subject(
            db, product_draft_id, submitted
        )
        credentials = resolve_integration_credentials(db, settings)
        if provider == "claude":
            client = ClaudeReviewClient(
                api_key=credentials.claude_api_key,
                model=settings.claude_model,
            )
        else:
            client = NvidiaReviewClient(
                api_key=credentials.nvidia_api_key,
                model=settings.nvidia_model,
            )
        price_config_id = active_provider_model_price_id(
            db,
            provider=provider,
            model=getattr(client, "model", ""),
        )
        db.commit()
        return draft_version, review_subject, client, price_config_id
    except HTTPException as exc:
        _finish_synchronous_review_job(db, review_job, error=exc)
        raise
    except Exception:
        _finish_unexpected_synchronous_review_job(db, review_job)
        raise


def _provider_review_subject(
    db: Session,
    product_draft_id: int | None,
    draft: ProductDraftCreate,
) -> DraftReviewSubject:
    if product_draft_id is None:
        return DraftReviewSubject(draft=draft)
    pricing = get_draft_pricing(db, product_draft_id)
    listing = get_draft_listing_config(db, product_draft_id)
    model = db.get(ProductDraft, product_draft_id)
    listing_errors = provider_review_context_errors(db, model) if model else []
    if listing_errors:
        raise HTTPException(
            status_code=409,
            detail={"code": "review_listing_context_incomplete", "errors": listing_errors},
        )
    return DraftReviewSubject(
        draft=draft,
        pricing=ReviewPricingContext(
            source_price=pricing.source_price,
            source_currency=pricing.source_currency,
            target_currency=pricing.target_currency,
            cost_currency=pricing.cost_currency,
            purchase_cost=pricing.purchase_cost,
            domestic_shipping_cost=pricing.domestic_shipping_cost,
            exchange_rate=pricing.exchange_rate,
            purchase_extra_cost=pricing.purchase_extra_cost,
            shipping_cost=pricing.shipping_cost,
            platform_fee_rate=pricing.platform_fee_rate,
            tax_rate=pricing.tax_rate,
            profit_margin_rate=pricing.profit_margin_rate,
            rounding_increment=pricing.rounding_increment,
            landed_cost=pricing.landed_cost,
            target_price=pricing.target_price,
        ),
        listing=ReviewListingContext(
            authorized_store_id=listing.store_id,
            site_id=listing.site_id,
            category_id=listing.category_id,
            listing_type_id=listing.listing_type_id,
            fulfillment=listing.fulfillment,
            shipping_mode=listing.shipping_mode,
            shipping_logistic_type=listing.shipping_logistic_type,
            attributes=listing.attributes_json or [],
        ),
    )


@router.get("/drafts/{product_draft_id}", response_model=list[ReviewResultRead])
def review_history(product_draft_id: int, db: Session = Depends(get_db)) -> list[ReviewResultRead]:
    return list_review_results(db, product_draft_id)


@router.get(
    "/drafts/{product_draft_id}/latest-behavioral",
    response_model=ReviewResultRead | None,
)
def latest_behavioral_review(
    product_draft_id: int,
    db: Session = Depends(get_db),
) -> ReviewResultRead | None:
    draft = db.get(ProductDraft, product_draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Product draft not found.")
    result = get_latest_behavioral_review(db, draft)
    return to_review_result_read(result) if result is not None else None


def _persist_if_requested(
    db: Session,
    response: ReviewResponse,
    product_draft_id: int | None,
    model: str = "",
    prompt_version: str = "",
    duration_ms: int = 0,
    expected_draft_version: int | None = None,
    price_config_id: int | None = None,
    price_config_captured: bool = False,
    review_job_id: int | None = None,
) -> ReviewResponse:
    if product_draft_id is None:
        cost = estimate_review_cost(
            db,
            provider=response.provider,
            model=model,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            price_config_id=price_config_id,
            price_config_captured=price_config_captured,
        )
        return response.model_copy(
            update={
                "price_config_id": cost.price_config_id,
                "estimated_cost_amount": cost.amount,
                "estimated_cost_currency": cost.currency,
            }
        )
    result = persist_review_result(
        db,
        product_draft_id,
        response,
        model=model,
        prompt_version=prompt_version,
        duration_ms=duration_ms,
        expected_draft_version=expected_draft_version,
        price_config_id=price_config_id,
        price_config_captured=price_config_captured,
        review_job_id=review_job_id,
    )
    return response.model_copy(
        update={
            "review_result_id": result.id,
            "price_config_id": result.price_config_id,
            "estimated_cost_amount": result.estimated_cost_amount,
            "estimated_cost_currency": result.estimated_cost_currency,
        }
    )


def _persist_provider_if_requested(
    db: Session,
    response: ReviewResponse,
    product_draft_id: int | None,
    model: str = "",
    prompt_version: str = "",
    duration_ms: int = 0,
    expected_draft_version: int | None = None,
    price_config_id: int | None = None,
    price_config_captured: bool = False,
    review_job_id: int | None = None,
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
            price_config_id=price_config_id,
            price_config_captured=price_config_captured,
            review_job_id=review_job_id,
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
            price_config_id=price_config_id,
            price_config_captured=price_config_captured,
            review_job_id=review_job_id,
        )
        raise


def _finish_synchronous_review_job(
    db: Session,
    job: ReviewJob | None,
    *,
    aggregate_review_result_id: int | None = None,
    error: HTTPException | None = None,
) -> None:
    if job is None:
        return
    if error is None:
        status = ReviewJobStatus.COMPLETED
        error_code = ""
        error_detail: dict = {}
        release_active_key = True
        next_attempt_at = None
    else:
        error_code, error_detail = _review_job_error_detail(error)
        failed = error.status_code == 429 or error.status_code >= 500
        status = ReviewJobStatus.FAILED if failed else ReviewJobStatus.BLOCKED
        release_active_key = not failed
        retry_after = error_detail.get("retry_after_seconds")
        delay = retry_after if isinstance(retry_after, int) and retry_after > 0 else 60
        next_attempt_at = datetime.now(UTC) + timedelta(seconds=delay) if failed else None
    complete_review_job(
        db,
        job,
        status=status,
        aggregate_review_result_id=aggregate_review_result_id,
        error_code=error_code,
        error_detail=error_detail,
        release_active_key=release_active_key,
        next_attempt_at=next_attempt_at,
    )
    audit_review_job_finished(db, job)
    db.commit()


def _finish_unexpected_synchronous_review_job(
    db: Session,
    job: ReviewJob | None,
) -> None:
    db.rollback()
    _finish_synchronous_review_job(
        db,
        job,
        error=HTTPException(
            status_code=500,
            detail={"code": "review_execution_failed"},
        ),
    )


def _review_job_error_detail(error: HTTPException) -> tuple[str, dict]:
    if isinstance(error.detail, dict):
        detail = {
            key: value
            for key, value in error.detail.items()
            if key in {
                "code",
                "provider",
                "retryable",
                "retry_after_seconds",
                "provider_http_status",
                "errors",
            }
        }
        return str(detail.get("code") or "review_blocked"), detail
    return str(error.detail), {}


def _reusable_job_provider_result(
    db: Session,
    *,
    review_job_id: int | None,
    provider: str,
    model: str,
    prompt_version: str,
    draft_version: int | None,
) -> ReviewResponse | None:
    if review_job_id is None or draft_version is None:
        return None
    result = db.scalar(
        select(ReviewResult)
        .where(
            ReviewResult.review_job_id == review_job_id,
            ReviewResult.provider == provider,
            ReviewResult.model == model,
            ReviewResult.prompt_version == prompt_version,
            ReviewResult.draft_version == draft_version,
            ReviewResult.provider_status == "completed",
        )
        .order_by(ReviewResult.id.desc())
        .limit(1)
    )
    if result is None:
        return None
    reasons = result.reasons_json or {}
    return ReviewResponse(
        provider=result.provider,
        decision=result.decision.value,
        risk_level=result.risk_level,
        reason_codes=reasons.get("reason_codes", []),
        reasons=reasons.get("reasons", []),
        suggested_changes=result.suggested_changes_json or {},
        review_result_id=result.id,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        total_tokens=result.total_tokens,
        provider_request_id=result.provider_request_id,
        price_config_id=result.price_config_id,
        estimated_cost_amount=result.estimated_cost_amount,
        estimated_cost_currency=result.estimated_cost_currency,
    )


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

    costs = [response.estimated_cost_amount for response in responses]
    currencies = {response.estimated_cost_currency for response in responses}
    estimated_cost_amount = sum(costs) if all(cost is not None for cost in costs) else None
    estimated_cost_currency = currencies.pop() if len(currencies) == 1 else ""
    if estimated_cost_amount is None:
        estimated_cost_currency = ""
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
        estimated_cost_amount=estimated_cost_amount,
        estimated_cost_currency=estimated_cost_currency,
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
    *,
    review_job_id: int | None = None,
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
            **({"review_job_id": review_job_id} if review_job_id is not None else {}),
        },
    )
