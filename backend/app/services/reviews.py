from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.product_draft import ProductDraft
from app.models.draft_listing_config import DraftListingConfig
from app.models.review_result import ReviewDecision, ReviewResult
from app.models.store import Store
from app.schemas.draft_listing_config import SUPPORTED_LISTING_TYPE_IDS
from app.schemas.reviews import ReviewResponse, ReviewResultRead
from app.services.ai.provider_utils import BEHAVIORAL_AUDIT_PROMPT_VERSION
from app.services.meli.category_validation import validate_category_attributes
from app.services.meli.payload_builder import (
    SUPPORTED_NON_FULL_LOGISTIC_TYPES,
    SUPPORTED_SHIPPING_MODES,
)
from app.services.audit_events import create_audit_event
from app.services.provider_pricing import ReviewCostSnapshot, estimate_review_cost


@dataclass(frozen=True)
class ReviewExecution:
    response: ReviewResponse
    model: str = ""
    prompt_version: str = ""
    duration_ms: int = 0
    provider_status: str = "completed"
    price_config_id: int | None = None
    price_config_captured: bool = False


@dataclass(frozen=True)
class ReviewBatchAudit:
    actor_type: str
    actor_id: str
    action: str
    after: dict


def persist_review_result(
    db: Session,
    product_draft_id: int,
    response: ReviewResponse,
    model: str = "",
    prompt_version: str = "",
    duration_ms: int = 0,
    provider_status: str = "completed",
    expected_draft_version: int | None = None,
    price_config_id: int | None = None,
    price_config_captured: bool = False,
) -> ReviewResult:
    return persist_review_results(
        db,
        product_draft_id,
        [
            ReviewExecution(
                response=response,
                model=model,
                prompt_version=prompt_version,
                duration_ms=duration_ms,
                provider_status=provider_status,
                price_config_id=price_config_id,
                price_config_captured=price_config_captured,
            )
        ],
        expected_draft_version=expected_draft_version,
    )[0]


def persist_stale_review_result(
    db: Session,
    product_draft_id: int,
    response: ReviewResponse,
    *,
    model: str = "",
    prompt_version: str = "",
    duration_ms: int = 0,
    draft_version: int,
    price_config_id: int | None = None,
    price_config_captured: bool = False,
) -> ReviewResult:
    draft = db.get(ProductDraft, product_draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail=f"Product draft {product_draft_id} not found.")
    cost = _review_cost_snapshot(
        db,
        response,
        model,
        price_config_id=price_config_id,
        price_config_captured=price_config_captured,
    )
    result = ReviewResult(
        product_draft_id=product_draft_id,
        provider=response.provider,
        model=model,
        prompt_version=prompt_version,
        duration_ms=max(0, duration_ms),
        provider_status="completed_stale",
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        total_tokens=response.total_tokens,
        provider_request_id=response.provider_request_id,
        price_config_id=cost.price_config_id,
        estimated_cost_amount=cost.amount,
        estimated_cost_currency=cost.currency,
        risk_level=response.risk_level,
        decision=ReviewDecision(response.decision),
        reasons_json={"reason_codes": response.reason_codes, "reasons": response.reasons},
        suggested_changes_json=response.suggested_changes,
        draft_version=draft_version,
    )
    db.add(result)
    db.flush()
    create_audit_event(
        db=db,
        actor_type="ai_provider",
        actor_id=response.provider,
        action="review.completed_stale",
        entity_type="product_draft",
        entity_id=str(product_draft_id),
        after={
            "review_result_id": result.id,
            "decision": response.decision,
            "risk_level": response.risk_level,
            "reason_codes": response.reason_codes,
            "model": model,
            "prompt_version": prompt_version,
            "duration_ms": duration_ms,
            "provider_status": "completed_stale",
            "reviewed_draft_version": draft_version,
            "current_draft_version": draft.content_version,
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
            "total_tokens": response.total_tokens,
            "provider_request_id": response.provider_request_id,
            "price_config_id": cost.price_config_id,
            "estimated_cost_amount": str(cost.amount) if cost.amount is not None else None,
            "estimated_cost_currency": cost.currency,
        },
        commit=False,
    )
    db.commit()
    db.refresh(result)
    return result


def persist_review_results(
    db: Session,
    product_draft_id: int,
    executions: list[ReviewExecution],
    expected_draft_version: int | None = None,
    batch_audit: ReviewBatchAudit | None = None,
) -> list[ReviewResult]:
    draft = db.get(ProductDraft, product_draft_id)
    if draft is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product draft {product_draft_id} not found.",
        )

    if any(
        execution.response.provider in {"claude", "nvidia", "claude+nvidia_behavioral_audit"}
        for execution in executions
    ):
        require_current_provider_review_context(db, draft, lock_store=True)

    draft_version = draft.content_version if expected_draft_version is None else expected_draft_version
    locked = db.execute(
        update(ProductDraft)
        .where(
            ProductDraft.id == product_draft_id,
            ProductDraft.content_version == draft_version,
        )
        .values(content_version=ProductDraft.content_version)
    )
    if locked.rowcount != 1:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="draft_content_version_changed_during_review",
        )

    costs = [
        _review_cost_snapshot(
            db,
            execution.response,
            execution.model,
            price_config_id=execution.price_config_id,
            price_config_captured=execution.price_config_captured,
        )
        for execution in executions
    ]
    results = [
        ReviewResult(
            product_draft_id=product_draft_id,
            provider=execution.response.provider,
            model=execution.model,
            prompt_version=execution.prompt_version,
            duration_ms=max(0, execution.duration_ms),
            provider_status=execution.provider_status,
            input_tokens=execution.response.input_tokens,
            output_tokens=execution.response.output_tokens,
            total_tokens=execution.response.total_tokens,
            provider_request_id=execution.response.provider_request_id,
            price_config_id=cost.price_config_id,
            estimated_cost_amount=cost.amount,
            estimated_cost_currency=cost.currency,
            risk_level=execution.response.risk_level,
            decision=ReviewDecision(execution.response.decision),
            reasons_json={
                "reason_codes": execution.response.reason_codes,
                "reasons": execution.response.reasons,
            },
            suggested_changes_json=execution.response.suggested_changes,
            draft_version=draft_version,
        )
        for execution, cost in zip(executions, costs, strict=True)
    ]
    db.add_all(results)
    db.flush()
    for result, execution in zip(results, executions, strict=True):
        response = execution.response
        create_audit_event(
            db=db,
            actor_type="ai_provider",
            actor_id=response.provider,
            action="review.completed",
            entity_type="product_draft",
            entity_id=str(product_draft_id),
            after={
                "review_result_id": result.id,
                "decision": response.decision,
                "risk_level": response.risk_level,
                "reason_codes": response.reason_codes,
                "model": execution.model,
                "prompt_version": execution.prompt_version,
                "duration_ms": execution.duration_ms,
                "provider_status": execution.provider_status,
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "total_tokens": response.total_tokens,
                "provider_request_id": response.provider_request_id,
                "price_config_id": result.price_config_id,
                "estimated_cost_amount": (
                    str(result.estimated_cost_amount)
                    if result.estimated_cost_amount is not None
                    else None
                ),
                "estimated_cost_currency": result.estimated_cost_currency,
            },
            commit=False,
        )
    if batch_audit is not None:
        create_audit_event(
            db=db,
            actor_type=batch_audit.actor_type,
            actor_id=batch_audit.actor_id,
            action=batch_audit.action,
            entity_type="product_draft",
            entity_id=str(product_draft_id),
            after={
                **batch_audit.after,
                "review_result_ids": [result.id for result in results],
            },
            commit=False,
        )
    db.commit()
    for result in results:
        db.refresh(result)
    return results


def get_publish_review(
    db: Session, product_draft_id: int, review_result_id: int | None
) -> ReviewResponse:
    if review_result_id is None:
        raise HTTPException(status_code=422, detail="persisted_behavioral_review_required")
    draft = db.get(ProductDraft, product_draft_id)
    result = db.get(ReviewResult, review_result_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Product draft not found.")
    if result is None or result.product_draft_id != product_draft_id:
        raise HTTPException(status_code=422, detail="persisted_behavioral_review_required")
    if result.draft_version != draft.content_version:
        raise HTTPException(status_code=422, detail="review_for_stale_draft_version")
    if result.provider != "claude+nvidia_behavioral_audit":
        raise HTTPException(status_code=422, detail="claude_nvidia_behavioral_review_required")
    latest = get_latest_behavioral_review(db, draft)
    if latest is None or latest.id != result.id:
        raise HTTPException(status_code=422, detail="latest_behavioral_review_required")
    return ReviewResponse(
        provider=result.provider,
        decision=result.decision.value,
        risk_level=result.risk_level,
        reason_codes=(result.reasons_json or {}).get("reason_codes", []),
        reasons=(result.reasons_json or {}).get("reasons", []),
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


def get_latest_behavioral_review(db: Session, draft: ProductDraft) -> ReviewResult | None:
    if provider_review_context_errors(db, draft):
        return None
    return db.scalar(
        select(ReviewResult)
        .where(
            ReviewResult.product_draft_id == draft.id,
            ReviewResult.draft_version == draft.content_version,
            ReviewResult.provider == "claude+nvidia_behavioral_audit",
            ReviewResult.prompt_version == BEHAVIORAL_AUDIT_PROMPT_VERSION,
        )
        .order_by(ReviewResult.id.desc())
        .limit(1)
    )


def provider_review_context_errors(
    db: Session, draft: ProductDraft, *, lock_store: bool = False
) -> list[str]:
    config = db.scalar(
        select(DraftListingConfig).where(
            DraftListingConfig.product_draft_id == draft.id
        )
    )
    if config is None:
        return ["saved_listing_configuration_required"]
    errors: list[str] = []
    if config.store_id is None:
        errors.append("authorized_store_selection_required")
        store = None
    else:
        store_statement = select(Store).where(Store.id == config.store_id)
        if lock_store:
            store_statement = store_statement.with_for_update()
        store = db.scalar(store_statement)
        if store is None:
            errors.append("authorized_store_not_found")
        else:
            if store.oauth_status != "connected":
                errors.append("store_not_connected")
            if store.site_id.strip().upper() != config.site_id.strip().upper():
                errors.append("store_site_mismatch")
    if config.site_id.strip().upper() != draft.target_site_id.strip().upper():
        errors.append("listing_site_mismatch")
    if config.listing_type_id not in SUPPORTED_LISTING_TYPE_IDS:
        errors.append("listing_type_not_supported")
    if config.fulfillment.strip().lower() == "full":
        errors.append("full_fulfillment_excluded")
    if config.shipping_mode not in SUPPORTED_SHIPPING_MODES:
        errors.append("non_full_shipping_mode_invalid")
    if config.shipping_logistic_type not in SUPPORTED_NON_FULL_LOGISTIC_TYPES:
        errors.append("non_full_shipping_logistic_type_invalid")
    if config.available_quantity is None or config.available_quantity < 1:
        errors.append("available_quantity_confirmation_required")
    errors.extend(
        validate_category_attributes(
            db,
            config.category_id,
            config.attributes_json or [],
            require_verified_metadata=True,
            require_item_condition=True,
        )
    )
    return list(dict.fromkeys(errors))


def require_current_provider_review_context(
    db: Session, draft: ProductDraft, *, lock_store: bool = False
) -> None:
    errors = provider_review_context_errors(db, draft, lock_store=lock_store)
    if errors:
        raise HTTPException(
            status_code=409,
            detail={"code": "review_listing_context_not_current", "errors": errors},
        )


def list_review_results(db: Session, product_draft_id: int) -> list[ReviewResultRead]:
    rows = db.scalars(
        select(ReviewResult)
        .where(ReviewResult.product_draft_id == product_draft_id)
        .order_by(ReviewResult.id.desc())
    ).all()
    return [to_review_result_read(row) for row in rows]


def to_review_result_read(result: ReviewResult) -> ReviewResultRead:
    reasons = result.reasons_json or {}
    return ReviewResultRead(
        id=result.id,
        product_draft_id=result.product_draft_id,
        provider=result.provider,
        model=result.model,
        prompt_version=result.prompt_version,
        duration_ms=result.duration_ms,
        provider_status=result.provider_status,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        total_tokens=result.total_tokens,
        provider_request_id=result.provider_request_id,
        price_config_id=result.price_config_id,
        estimated_cost_amount=result.estimated_cost_amount,
        estimated_cost_currency=result.estimated_cost_currency,
        decision=result.decision.value,
        risk_level=result.risk_level,
        reason_codes=reasons.get("reason_codes", []),
        reasons=reasons.get("reasons", []),
        suggested_changes=result.suggested_changes_json or {},
        created_at=result.created_at,
    )


def _review_cost_snapshot(
    db: Session,
    response: ReviewResponse,
    model: str,
    *,
    price_config_id: int | None = None,
    price_config_captured: bool = False,
) -> ReviewCostSnapshot:
    if (
        response.provider == "claude+nvidia_behavioral_audit"
        and response.estimated_cost_amount is not None
    ):
        return ReviewCostSnapshot(
            amount=response.estimated_cost_amount,
            currency=response.estimated_cost_currency,
        )
    return estimate_review_cost(
        db,
        provider=response.provider,
        model=model,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        price_config_id=price_config_id,
        price_config_captured=price_config_captured,
    )
