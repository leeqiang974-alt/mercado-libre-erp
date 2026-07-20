from datetime import UTC, datetime, timedelta
import hashlib
import json

from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.publish_job import PublishJob, PublishJobStatus
from app.schemas.drafts import ProductDraftCreate
from app.schemas.publishing import ListingChoice, PublishExecutionResult, PublishJobRead
from app.schemas.reviews import ReviewResponse
from app.services.audit_events import create_audit_event


def _utc_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def create_publish_job(
    db: Session,
    product_draft_id: int,
    store_id: int,
    requested_by: str,
    draft: ProductDraftCreate,
    review: ReviewResponse,
    listing_choice: ListingChoice,
    valid_listing_type_ids: list[str] | None = None,
    initial_status: PublishJobStatus = PublishJobStatus.PENDING,
    commit: bool = True,
) -> PublishJob:
    idempotency_key = _publish_idempotency_key(
        product_draft_id,
        store_id,
        draft,
        review,
        listing_choice,
    )
    if db.get_bind().dialect.name == "postgresql":
        db.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:lock_name))"),
            {"lock_name": f"publish_job:{idempotency_key}"},
        )
    existing = (
        db.query(PublishJob)
        .filter(PublishJob.idempotency_key == idempotency_key)
        .one_or_none()
    )
    if existing is not None:
        existing._idempotent_replay = True
        return existing
    job = PublishJob(
        product_draft_id=product_draft_id,
        store_id=store_id,
        requested_by=requested_by,
        idempotency_key=idempotency_key,
        status=initial_status,
        started_at=datetime.now(UTC) if initial_status == PublishJobStatus.VALIDATING else None,
        request_summary_json={
            "title": draft.title,
            "site_id": draft.target_site_id,
            "store_id": listing_choice.store_id,
            "category_id": draft.target_category_id,
            "listing_type_id": listing_choice.listing_type_id,
            "valid_listing_type_ids": valid_listing_type_ids or [listing_choice.listing_type_id],
            "fulfillment": listing_choice.fulfillment,
            "shipping_mode": listing_choice.shipping_mode,
            "shipping_logistic_type": listing_choice.shipping_logistic_type,
            "review_provider": review.provider,
            "review_result_id": review.review_result_id,
            "review_decision": review.decision,
            "review_risk_level": review.risk_level,
            "review_reason_codes": review.reason_codes,
            "review_reasons": review.reasons,
            "review_suggested_changes": review.suggested_changes,
        },
    )
    db.add(job)
    if not commit:
        db.flush()
        return job
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = (
            db.query(PublishJob)
            .filter(PublishJob.idempotency_key == idempotency_key)
            .one_or_none()
        )
        if existing is None:
            raise
        existing._idempotent_replay = True
        return existing
    db.refresh(job)
    return job


def _publish_idempotency_key(
    product_draft_id: int,
    store_id: int,
    draft: ProductDraftCreate,
    review: ReviewResponse,
    listing_choice: ListingChoice,
) -> str:
    payload = {
        "product_draft_id": product_draft_id,
        "store_id": store_id,
        "draft": draft.model_dump(mode="json"),
        "review_result_id": review.review_result_id,
        "listing_choice": listing_choice.model_dump(mode="json"),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def replay_publish_result(job: PublishJob) -> PublishExecutionResult:
    if job.status in {PublishJobStatus.PENDING, PublishJobStatus.VALIDATING}:
        return PublishExecutionResult(
            status="blocked",
            errors=["publish_already_in_progress"],
            job_id=job.id,
        )
    summary = job.response_summary_json or {}
    return PublishExecutionResult(
        status=summary.get("status", job.status.value),
        item_id=job.meli_item_id,
        permalink=job.permalink,
        shipping_mode=summary.get("shipping_mode", ""),
        shipping_logistic_type=summary.get("shipping_logistic_type", ""),
        errors=summary.get("errors", []),
        job_id=job.id,
    )


def publish_blocking_errors(detail: object) -> list[str]:
    if isinstance(detail, dict):
        errors = detail.get("errors")
        if isinstance(errors, list) and errors:
            return [str(error) for error in errors]
        if detail.get("code"):
            return [str(detail["code"])]
    if isinstance(detail, list):
        return [str(error) for error in detail]
    return [str(detail)]


def complete_publish_job(db: Session, job: PublishJob, result: PublishExecutionResult) -> PublishJob:
    if result.item_id:
        job.meli_item_id = result.item_id
    if result.permalink:
        job.permalink = result.permalink
    if result.status == "published":
        job.status = PublishJobStatus.PUBLISHED
    elif result.status == "blocked":
        job.status = PublishJobStatus.BLOCKED
    else:
        job.status = PublishJobStatus.FAILED
    job.response_summary_json = {
        "status": result.status,
        "item_id": result.item_id,
        "permalink": result.permalink,
        "shipping_mode": result.shipping_mode,
        "shipping_logistic_type": result.shipping_logistic_type,
        "errors": result.errors,
    }
    job.completed_at = datetime.now(UTC)
    db.commit()
    db.refresh(job)
    return job


def cancel_publish_job(db: Session, job_id: int, *, cancelled_by: str) -> PublishJob:
    existing = db.get(PublishJob, job_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Publish job not found.")
    if existing.status == PublishJobStatus.CANCELLED:
        return existing

    original_idempotency_key = existing.idempotency_key
    if db.get_bind().dialect.name == "postgresql":
        db.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:lock_name))"),
            {"lock_name": f"publish_job:{original_idempotency_key}"},
        )
    job = db.scalar(
        select(PublishJob)
        .where(PublishJob.id == job_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if job is None:
        raise HTTPException(status_code=404, detail="Publish job not found.")
    if job.status == PublishJobStatus.CANCELLED:
        return job
    if job.status != PublishJobStatus.PENDING:
        raise HTTPException(
            status_code=409,
            detail="Only pending publish jobs can be cancelled.",
        )

    job.status = PublishJobStatus.CANCELLED
    job.idempotency_key = hashlib.sha256(
        f"cancelled:{job.id}:{original_idempotency_key}".encode()
    ).hexdigest()
    job.response_summary_json = {
        "status": "cancelled",
        "item_id": "",
        "permalink": "",
        "shipping_mode": "",
        "shipping_logistic_type": "",
        "errors": ["publish_cancelled_by_operator"],
    }
    job.completed_at = datetime.now(UTC)
    create_audit_event(
        db=db,
        actor_type="operator",
        actor_id=cancelled_by,
        action="publish.cancelled",
        entity_type="publish_job",
        entity_id=str(job.id),
        before={"status": PublishJobStatus.PENDING.value},
        after={
            "status": PublishJobStatus.CANCELLED.value,
            "product_draft_id": job.product_draft_id,
            "store_id": job.store_id,
        },
        commit=False,
    )
    db.commit()
    db.refresh(job)
    return job


def recover_stale_publish_jobs(db: Session, stale_after_seconds: int) -> int:
    cutoff = datetime.now(UTC) - timedelta(seconds=stale_after_seconds)
    jobs = (
        db.query(PublishJob)
        .filter(
            PublishJob.status == PublishJobStatus.VALIDATING,
            PublishJob.started_at.is_not(None),
            PublishJob.started_at < cutoff,
        )
        .all()
    )
    for job in jobs:
        job.status = PublishJobStatus.BLOCKED
        job.response_summary_json = {
            "status": "blocked",
            "item_id": job.meli_item_id,
            "permalink": job.permalink,
            "shipping_mode": "",
            "shipping_logistic_type": "",
            "errors": ["publish_outcome_unknown_manual_reconciliation_required"],
        }
        job.completed_at = datetime.now(UTC)
    if jobs:
        db.commit()
    return len(jobs)


def to_publish_job_read(job: PublishJob) -> PublishJobRead:
    response_summary = job.response_summary_json or {}
    return PublishJobRead(
        id=job.id,
        product_draft_id=job.product_draft_id,
        store_id=job.store_id,
        status=job.status.value if hasattr(job.status, "value") else str(job.status),
        item_id=job.meli_item_id,
        permalink=job.permalink,
        shipping_mode=response_summary.get("shipping_mode", ""),
        shipping_logistic_type=response_summary.get("shipping_logistic_type", ""),
        errors=response_summary.get("errors", []),
        created_at=_utc_datetime(job.created_at),
        started_at=_utc_datetime(job.started_at),
        completed_at=_utc_datetime(job.completed_at),
    )


def list_publish_jobs(db: Session, *, limit: int = 100, offset: int = 0) -> list[PublishJobRead]:
    jobs = (
        db.query(PublishJob)
        .order_by(PublishJob.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [to_publish_job_read(job) for job in jobs]


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
