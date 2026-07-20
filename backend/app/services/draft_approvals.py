from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.product_draft import ProductDraft
from app.models.product_draft_approval import ProductDraftApproval
from app.models.review_result import ReviewDecision
from app.schemas.draft_approvals import DraftApprovalCreate, DraftApprovalRead
from app.services.audit_events import create_audit_event
from app.services.reviews import get_latest_behavioral_review


def approve_product_draft(
    db: Session,
    product_draft_id: int,
    payload: DraftApprovalCreate,
) -> ProductDraftApproval:
    draft = db.get(ProductDraft, product_draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Product draft not found.")
    behavioral_review = get_latest_behavioral_review(db, draft)
    if behavioral_review is None or behavioral_review.decision != ReviewDecision.PASS:
        raise HTTPException(
            status_code=422,
            detail="current_claude_nvidia_pass_required_before_approval",
        )

    approval = (
        db.query(ProductDraftApproval)
        .filter(ProductDraftApproval.product_draft_id == product_draft_id)
        .one_or_none()
    )
    if approval is None:
        approval = ProductDraftApproval(product_draft_id=product_draft_id)
        db.add(approval)
    approval.status = "approved"
    approval.review_result_id = behavioral_review.id
    approval.approved_by = payload.approved_by
    approval.note = payload.note
    approval.draft_version = draft.content_version
    approval.approved_at = datetime.now(UTC)
    db.commit()
    db.refresh(approval)
    create_audit_event(
        db=db,
        actor_type="operator",
        actor_id=payload.approved_by,
        action="draft.approved",
        entity_type="product_draft",
        entity_id=str(product_draft_id),
        after={
            "approval_id": approval.id,
            "review_result_id": behavioral_review.id,
            "status": approval.status,
            "approved_by": approval.approved_by,
        },
    )
    return approval


def get_product_draft_approval(db: Session, product_draft_id: int) -> ProductDraftApproval | None:
    return (
        db.query(ProductDraftApproval)
        .filter(
            ProductDraftApproval.product_draft_id == product_draft_id,
            ProductDraftApproval.status == "approved",
        )
        .one_or_none()
    )


def is_product_draft_approved(db: Session, product_draft_id: int) -> bool:
    draft = db.get(ProductDraft, product_draft_id)
    approval = get_product_draft_approval(db, product_draft_id)
    if not draft or not approval or approval.draft_version != draft.content_version:
        return False
    review = get_latest_behavioral_review(db, draft)
    return bool(
        review
        and review.decision == ReviewDecision.PASS
        and approval.review_result_id == review.id
    )


def to_approval_read(approval: ProductDraftApproval) -> DraftApprovalRead:
    return DraftApprovalRead(
        id=approval.id,
        product_draft_id=approval.product_draft_id,
        review_result_id=approval.review_result_id,
        status=approval.status,
        approved_by=approval.approved_by,
        note=approval.note,
        approved_at=approval.approved_at,
    )
