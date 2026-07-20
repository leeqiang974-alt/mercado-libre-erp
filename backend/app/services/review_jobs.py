from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.product_draft import ProductDraft
from app.models.review_job import ReviewJob, ReviewJobStatus
from app.schemas.reviews import (
    ReviewJobBatchItem,
    ReviewJobBatchResponse,
    ReviewJobRead,
)
from app.services.audit_events import create_audit_event
from app.services.draft_pricing import require_current_draft_pricing
from app.services.reviews import get_latest_behavioral_review, provider_review_context_errors

def enqueue_review_batch(
    db: Session,
    draft_ids: list[int],
    *,
    requested_by: str = "operator",
    _retry_on_conflict: bool = True,
) -> ReviewJobBatchResponse:
    batch_id = str(uuid4())
    items: list[ReviewJobBatchItem] = []
    for draft_id in draft_ids:
        draft = db.get(ProductDraft, draft_id)
        if draft is None:
            items.append(ReviewJobBatchItem(draft_id=draft_id, outcome="not_found"))
            continue
        errors = _review_readiness_errors(db, draft)
        if errors:
            items.append(
                ReviewJobBatchItem(
                    draft_id=draft_id,
                    outcome="not_ready",
                    errors=errors,
                )
            )
            continue
        active_key = f"combined:{draft_id}"
        existing = db.scalar(select(ReviewJob).where(ReviewJob.active_key == active_key))
        if existing is not None:
            if (
                existing.status == ReviewJobStatus.FAILED
                and existing.draft_version != draft.content_version
            ):
                existing.active_key = None
                db.flush()
                existing = None
        if existing is not None:
            if (
                existing.status == ReviewJobStatus.FAILED
                and existing.draft_version == draft.content_version
            ):
                pause_until = _provider_pause_until(db)
                existing.status = ReviewJobStatus.PENDING
                existing.error_code = ""
                existing.error_detail_json = {}
                existing.started_at = None
                existing.completed_at = None
                existing.next_attempt_at = pause_until
                db.flush()
                items.append(
                    ReviewJobBatchItem(
                        draft_id=draft_id,
                        outcome="queued",
                        job=to_review_job_read(existing),
                    )
                )
                continue
            items.append(
                ReviewJobBatchItem(
                    draft_id=draft_id,
                    outcome="existing",
                    job=to_review_job_read(existing),
                )
            )
            continue
        job = ReviewJob(
            batch_id=batch_id,
            product_draft_id=draft_id,
            requested_by=requested_by,
            draft_version=draft.content_version,
            baseline_review_result_id=(
                latest.id if (latest := get_latest_behavioral_review(db, draft)) else None
            ),
            active_key=active_key,
            next_attempt_at=_provider_pause_until(db),
        )
        db.add(job)
        try:
            db.flush()
        except IntegrityError as exc:
            db.rollback()
            if _retry_on_conflict:
                return enqueue_review_batch(
                    db,
                    draft_ids,
                    requested_by=requested_by,
                    _retry_on_conflict=False,
                )
            existing = db.scalar(select(ReviewJob).where(ReviewJob.active_key == active_key))
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "review_enqueue_conflict_retry_required",
                    "draft_id": draft_id,
                    "job_id": existing.id if existing is not None else None,
                },
            ) from exc
        items.append(
            ReviewJobBatchItem(
                draft_id=draft_id,
                outcome="queued",
                job=to_review_job_read(job),
            )
        )

    response = ReviewJobBatchResponse(
        batch_id=batch_id,
        queued_count=sum(item.outcome == "queued" for item in items),
        existing_count=sum(item.outcome == "existing" for item in items),
        not_ready_count=sum(item.outcome == "not_ready" for item in items),
        not_found_count=sum(item.outcome == "not_found" for item in items),
        items=items,
    )
    create_audit_event(
        db=db,
        actor_type="operator",
        actor_id=requested_by,
        action="review.batch.queued",
        entity_type="review_batch",
        entity_id=batch_id,
        after={
            "draft_ids": draft_ids,
            "acknowledge_provider_costs": True,
            "queued_count": response.queued_count,
            "existing_count": response.existing_count,
            "not_ready_count": response.not_ready_count,
            "not_found_count": response.not_found_count,
        },
        commit=False,
    )
    db.commit()
    return response


def list_review_jobs(db: Session, *, limit: int = 100) -> list[ReviewJobRead]:
    jobs = db.scalars(select(ReviewJob).order_by(ReviewJob.id.desc()).limit(limit)).all()
    return [to_review_job_read(job) for job in jobs]


def start_synchronous_review_job(
    db: Session,
    product_draft_id: int | None,
    *,
    acknowledge_provider_costs: bool = False,
) -> ReviewJob | None:
    if product_draft_id is None:
        return None
    draft = db.get(ProductDraft, product_draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Product draft not found.")
    errors = _review_readiness_errors(db, draft)
    if errors:
        raise HTTPException(
            status_code=409,
            detail={"code": "review_listing_context_incomplete", "errors": errors},
        )
    active_key = f"combined:{product_draft_id}"
    existing = db.scalar(select(ReviewJob).where(ReviewJob.active_key == active_key))
    if (
        existing is not None
        and existing.status == ReviewJobStatus.FAILED
        and existing.draft_version != draft.content_version
    ):
        existing.active_key = None
        db.flush()
        existing = None
    if existing is not None:
        if (
            existing.status == ReviewJobStatus.FAILED
            and existing.draft_version == draft.content_version
        ):
            if not acknowledge_provider_costs:
                raise HTTPException(
                    status_code=422,
                    detail={"code": "provider_cost_acknowledgement_required"},
                )
            pause_until = _aware_utc(existing.next_attempt_at)
            now = datetime.now(UTC)
            if pause_until is not None and pause_until > now:
                raise HTTPException(
                    status_code=429,
                    detail={
                        "code": "provider_retry_window_active",
                        "retry_after_seconds": max(
                            1, int((pause_until - now).total_seconds())
                        ),
                    },
                )
            existing.status = ReviewJobStatus.RUNNING
            existing.error_code = ""
            existing.error_detail_json = {}
            existing.next_attempt_at = None
            existing.started_at = datetime.now(UTC)
            existing.completed_at = None
            db.commit()
            db.refresh(existing)
            return existing
        raise HTTPException(
            status_code=409,
            detail={"code": "review_already_queued_or_running", "job_id": existing.id},
        )
    job = ReviewJob(
        batch_id=str(uuid4()),
        product_draft_id=product_draft_id,
        requested_by="synchronous_api",
        draft_version=draft.content_version,
        baseline_review_result_id=(
            latest.id if (latest := get_latest_behavioral_review(db, draft)) else None
        ),
        active_key=active_key,
        status=ReviewJobStatus.RUNNING,
        started_at=datetime.now(UTC),
    )
    db.add(job)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        active = db.scalar(select(ReviewJob).where(ReviewJob.active_key == active_key))
        raise HTTPException(
            status_code=409,
            detail={
                "code": "review_already_queued_or_running",
                "job_id": active.id if active is not None else None,
            },
        ) from None
    db.refresh(job)
    return job


def complete_review_job(
    db: Session,
    job: ReviewJob,
    *,
    status: ReviewJobStatus,
    aggregate_review_result_id: int | None = None,
    error_code: str = "",
    error_detail: dict | None = None,
    release_active_key: bool = True,
    next_attempt_at: datetime | None = None,
) -> ReviewJob:
    job.status = status
    job.aggregate_review_result_id = aggregate_review_result_id
    job.error_code = error_code
    job.error_detail_json = error_detail or {}
    if release_active_key:
        job.active_key = None
    job.next_attempt_at = next_attempt_at
    job.completed_at = datetime.now(UTC)
    return job


def recover_stale_review_jobs(db: Session, stale_after_seconds: int) -> int:
    cutoff = datetime.now(UTC) - timedelta(seconds=stale_after_seconds)
    jobs = db.scalars(
        select(ReviewJob)
        .where(
            ReviewJob.status == ReviewJobStatus.RUNNING,
            ReviewJob.started_at.is_not(None),
            ReviewJob.started_at < cutoff,
        )
        .with_for_update(skip_locked=True)
    ).all()
    for job in jobs:
        draft = db.get(ProductDraft, job.product_draft_id)
        latest = get_latest_behavioral_review(db, draft) if draft is not None else None
        if latest is not None and latest.id != job.baseline_review_result_id:
            job.status = ReviewJobStatus.COMPLETED
            job.aggregate_review_result_id = latest.id
            job.error_code = ""
            job.error_detail_json = {"recovered_persisted_review": True}
        else:
            job.status = ReviewJobStatus.FAILED
            job.error_code = "review_worker_interrupted_manual_retry_required"
            job.error_detail_json = {"automatic_retry": False}
        if job.status == ReviewJobStatus.COMPLETED:
            job.active_key = None
        job.completed_at = datetime.now(UTC)
        audit_review_job_finished(db, job, recovered=True)
    if jobs:
        db.commit()
    return len(jobs)


def to_review_job_read(job: ReviewJob) -> ReviewJobRead:
    return ReviewJobRead(
        id=job.id,
        batch_id=job.batch_id,
        product_draft_id=job.product_draft_id,
        draft_version=job.draft_version,
        status=job.status.value if hasattr(job.status, "value") else str(job.status),
        aggregate_review_result_id=job.aggregate_review_result_id,
        error_code=job.error_code,
        error_detail=job.error_detail_json or {},
        created_at=job.created_at,
        next_attempt_at=job.next_attempt_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )


def _review_readiness_errors(db: Session, draft: ProductDraft) -> list[str]:
    errors = provider_review_context_errors(db, draft)
    try:
        require_current_draft_pricing(db, draft)
    except HTTPException as exc:
        detail = exc.detail
        if isinstance(detail, dict) and isinstance(detail.get("errors"), list):
            errors.extend(str(error) for error in detail["errors"])
        elif isinstance(detail, dict) and detail.get("code"):
            errors.append(str(detail["code"]))
        else:
            errors.append(str(detail))
    return list(dict.fromkeys(errors))


def _provider_pause_until(db: Session) -> datetime | None:
    return db.scalar(
        select(func.max(ReviewJob.next_attempt_at)).where(
            ReviewJob.next_attempt_at.is_not(None),
            ReviewJob.next_attempt_at > datetime.now(UTC),
        )
    )


def _aware_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def audit_review_job_finished(
    db: Session,
    job: ReviewJob,
    *,
    recovered: bool = False,
) -> None:
    create_audit_event(
        db=db,
        actor_type="worker",
        actor_id="review_worker",
        action="review.job.finished",
        entity_type="review_job",
        entity_id=str(job.id),
        before={
            "batch_id": job.batch_id,
            "product_draft_id": job.product_draft_id,
        },
        after={
            "status": job.status.value,
            "aggregate_review_result_id": job.aggregate_review_result_id,
            "error_code": job.error_code,
            "error_detail": job.error_detail_json or {},
            "recovered": recovered,
        },
        commit=False,
    )
