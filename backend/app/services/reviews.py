from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.product_draft import ProductDraft
from app.models.review_result import ReviewDecision, ReviewResult
from app.schemas.reviews import ReviewResponse, ReviewResultRead


def persist_review_result(
    db: Session,
    product_draft_id: int,
    response: ReviewResponse,
    model: str = "",
) -> ReviewResult:
    draft = db.get(ProductDraft, product_draft_id)
    if draft is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product draft {product_draft_id} not found.",
        )

    result = ReviewResult(
        product_draft_id=product_draft_id,
        provider=response.provider,
        model=model,
        risk_level=response.risk_level,
        decision=ReviewDecision(response.decision),
        reasons_json={
            "reason_codes": response.reason_codes,
            "reasons": response.reasons,
        },
        suggested_changes_json=response.suggested_changes,
    )
    db.add(result)
    db.commit()
    db.refresh(result)
    return result


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
        decision=result.decision.value,
        risk_level=result.risk_level,
        reason_codes=reasons.get("reason_codes", []),
        reasons=reasons.get("reasons", []),
        suggested_changes=result.suggested_changes_json or {},
    )
