from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.product_draft import ProductDraft
from app.models.review_result import ReviewDecision, ReviewResult
from app.schemas.reviews import ReviewResponse, ReviewResultRead
from app.services.audit_events import create_audit_event


@dataclass(frozen=True)
class ReviewExecution:
    response: ReviewResponse
    model: str = ""
    prompt_version: str = ""
    duration_ms: int = 0
    provider_status: str = "completed"


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
            )
        ],
        expected_draft_version=expected_draft_version,
    )[0]


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

    results = [
        ReviewResult(
            product_draft_id=product_draft_id,
            provider=execution.response.provider,
            model=execution.model,
            prompt_version=execution.prompt_version,
            duration_ms=max(0, execution.duration_ms),
            provider_status=execution.provider_status,
            risk_level=execution.response.risk_level,
            decision=ReviewDecision(execution.response.decision),
            reasons_json={
                "reason_codes": execution.response.reason_codes,
                "reasons": execution.response.reasons,
            },
            suggested_changes_json=execution.response.suggested_changes,
            draft_version=draft_version,
        )
        for execution in executions
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
    )


def get_latest_behavioral_review(db: Session, draft: ProductDraft) -> ReviewResult | None:
    return db.scalar(
        select(ReviewResult)
        .where(
            ReviewResult.product_draft_id == draft.id,
            ReviewResult.draft_version == draft.content_version,
            ReviewResult.provider == "claude+nvidia_behavioral_audit",
        )
        .order_by(ReviewResult.id.desc())
        .limit(1)
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
        decision=result.decision.value,
        risk_level=result.risk_level,
        reason_codes=reasons.get("reason_codes", []),
        reasons=reasons.get("reasons", []),
        suggested_changes=result.suggested_changes_json or {},
        created_at=result.created_at,
    )
