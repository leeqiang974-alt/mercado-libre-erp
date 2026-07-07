from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.publish_job import PublishJob, PublishJobStatus
from app.schemas.drafts import ProductDraftCreate
from app.schemas.publishing import ListingChoice, PublishExecutionResult, PublishJobRead
from app.schemas.reviews import ReviewResponse


def create_publish_job(
    db: Session,
    product_draft_id: int,
    store_id: int,
    requested_by: str,
    draft: ProductDraftCreate,
    review: ReviewResponse,
    listing_choice: ListingChoice,
) -> PublishJob:
    job = PublishJob(
        product_draft_id=product_draft_id,
        store_id=store_id,
        requested_by=requested_by,
        status=PublishJobStatus.PENDING,
        request_summary_json={
            "title": draft.title,
            "site_id": draft.target_site_id,
            "category_id": draft.target_category_id,
            "listing_type_id": listing_choice.listing_type_id,
            "fulfillment": listing_choice.fulfillment,
            "review_provider": review.provider,
            "review_decision": review.decision,
            "review_risk_level": review.risk_level,
            "review_reason_codes": review.reason_codes,
            "review_reasons": review.reasons,
            "review_suggested_changes": review.suggested_changes,
        },
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def complete_publish_job(db: Session, job: PublishJob, result: PublishExecutionResult) -> PublishJob:
    if result.status == "published":
        job.status = PublishJobStatus.PUBLISHED
        job.meli_item_id = result.item_id
        job.permalink = result.permalink
    elif result.status == "blocked":
        job.status = PublishJobStatus.BLOCKED
    else:
        job.status = PublishJobStatus.FAILED
    job.response_summary_json = {
        "status": result.status,
        "item_id": result.item_id,
        "permalink": result.permalink,
        "errors": result.errors,
    }
    job.completed_at = datetime.now(UTC)
    db.commit()
    db.refresh(job)
    return job


def to_publish_job_read(job: PublishJob) -> PublishJobRead:
    response_summary = job.response_summary_json or {}
    return PublishJobRead(
        id=job.id,
        product_draft_id=job.product_draft_id,
        store_id=job.store_id,
        status=job.status.value if hasattr(job.status, "value") else str(job.status),
        item_id=job.meli_item_id,
        permalink=job.permalink,
        errors=response_summary.get("errors", []),
    )


def list_publish_jobs(db: Session) -> list[PublishJobRead]:
    return [to_publish_job_read(job) for job in db.query(PublishJob).order_by(PublishJob.id.desc()).all()]


def get_publish_job_or_404(db: Session, job_id: int) -> PublishJob:
    job = db.get(PublishJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Publish job not found.")
    return job


def review_from_job_summary(job: PublishJob) -> ReviewResponse:
    summary = job.request_summary_json or {}
    return ReviewResponse(
        provider=summary.get("review_provider", "previous_review"),
        decision=summary.get("review_decision", "needs_changes"),
        risk_level=summary.get("review_risk_level", "medium"),
        reason_codes=summary.get("review_reason_codes", []),
        reasons=summary.get("review_reasons", []),
        suggested_changes=summary.get("review_suggested_changes", {}),
    )
