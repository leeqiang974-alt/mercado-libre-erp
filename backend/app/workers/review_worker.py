from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.review_job import ReviewJob, ReviewJobStatus
from app.models.product_draft import ProductDraft
from app.schemas.reviews import BehavioralAuditResponse, ReviewJobRead
from app.services.review_jobs import (
    audit_review_job_finished,
    complete_review_job,
    recover_stale_review_jobs,
    to_review_job_read,
)
from app.services.reviews import get_latest_behavioral_review

Reviewer = Callable[[Session, int], Awaitable[BehavioralAuditResponse]]
WorkerSummary = dict[str, int]
_PROVIDER_PAUSE_CODES = {
    "rate_limited",
    "provider_unavailable",
    "provider_unreachable",
}


async def run_pending_review_jobs(
    db: Session,
    *,
    limit: int = 5,
    reviewer: Reviewer | None = None,
) -> WorkerSummary:
    recovered = recover_stale_review_jobs(db, get_settings().job_stale_after_seconds)
    now = datetime.now(UTC)
    job_ids = db.scalars(
        select(ReviewJob.id)
        .where(
            ReviewJob.status == ReviewJobStatus.PENDING,
            or_(ReviewJob.next_attempt_at.is_(None), ReviewJob.next_attempt_at <= now),
        )
        .order_by(ReviewJob.id)
        .limit(limit)
    ).all()
    summary = {
        "processed": 0,
        "completed": 0,
        "blocked": 0,
        "failed": 0,
        "recovered": recovered,
    }
    for job_id in job_ids:
        try:
            result = await run_pending_review_job(db, job_id=job_id, reviewer=reviewer)
        except HTTPException as exc:
            if exc.status_code != 409:
                raise
            db.rollback()
            continue
        summary["processed"] += 1
        summary[result.status] += 1
        if result.error_code in _PROVIDER_PAUSE_CODES:
            _pause_pending_jobs(db, result.error_detail)
            break
    return summary


async def run_pending_review_job(
    db: Session,
    *,
    job_id: int,
    reviewer: Reviewer | None = None,
) -> ReviewJobRead:
    job = db.scalar(
        select(ReviewJob)
        .where(
            ReviewJob.id == job_id,
            ReviewJob.status == ReviewJobStatus.PENDING,
        )
        .with_for_update(skip_locked=True)
    )
    if job is None:
        existing = db.get(ReviewJob, job_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="Review job not found.")
        raise HTTPException(status_code=409, detail="Review job was claimed by another worker.")

    job.status = ReviewJobStatus.RUNNING
    job.started_at = datetime.now(UTC)
    job.next_attempt_at = None
    db.commit()
    db.refresh(job)

    draft = db.get(ProductDraft, job.product_draft_id)
    if draft is None or draft.content_version != job.draft_version:
        complete_review_job(
            db,
            job,
            status=ReviewJobStatus.BLOCKED,
            error_code=(
                "product_draft_not_found"
                if draft is None
                else "draft_content_changed_after_review_queued"
            ),
            error_detail={"queued_draft_version": job.draft_version},
        )
        audit_review_job_finished(db, job)
        db.commit()
        return to_review_job_read(job)
    latest = get_latest_behavioral_review(db, draft)
    if latest is not None and latest.id != job.baseline_review_result_id:
        complete_review_job(
            db,
            job,
            status=ReviewJobStatus.COMPLETED,
            aggregate_review_result_id=latest.id,
            error_detail={"reused_persisted_review": True},
        )
        audit_review_job_finished(db, job)
        db.commit()
        return to_review_job_read(job)

    try:
        audit = (
            await reviewer(db, job.product_draft_id)
            if reviewer is not None
            else await _default_reviewer(db, job.product_draft_id, job.id)
        )
        aggregate_id = audit.aggregate.review_result_id
        if aggregate_id is None:
            raise RuntimeError("aggregate review was not persisted")
        status = ReviewJobStatus.COMPLETED
        error_code = ""
        error_detail: dict = {}
    except HTTPException as exc:
        error_code, error_detail = _http_error_detail(exc)
        status = (
            ReviewJobStatus.FAILED
            if error_code in _PROVIDER_PAUSE_CODES or exc.status_code >= 500
            else ReviewJobStatus.BLOCKED
        )
        aggregate_id = None
        db.rollback()
    except Exception as exc:
        status = ReviewJobStatus.FAILED
        error_code = f"review_worker_error:{type(exc).__name__}"
        error_detail = {}
        aggregate_id = None
        db.rollback()

    job = db.get(ReviewJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Review job not found.")
    complete_review_job(
        db,
        job,
        status=status,
        aggregate_review_result_id=aggregate_id,
        error_code=error_code,
        error_detail=error_detail,
        release_active_key=status != ReviewJobStatus.FAILED,
        next_attempt_at=_retry_at(error_detail) if status == ReviewJobStatus.FAILED else None,
    )
    audit_review_job_finished(db, job)
    db.commit()
    return to_review_job_read(job)


async def _default_reviewer(
    db: Session,
    product_draft_id: int,
    review_job_id: int,
) -> BehavioralAuditResponse:
    from app.api.routes.reviews import run_behavioral_audit_for_draft

    return await run_behavioral_audit_for_draft(db, product_draft_id, review_job_id)


def _http_error_detail(exc: HTTPException) -> tuple[str, dict]:
    if isinstance(exc.detail, dict):
        detail = {
            key: value
            for key, value in exc.detail.items()
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
    return str(exc.detail), {}


def _pause_pending_jobs(db: Session, error_detail: dict) -> None:
    pause_until = _retry_at(error_detail)
    db.execute(
        update(ReviewJob)
        .where(ReviewJob.status == ReviewJobStatus.PENDING)
        .values(next_attempt_at=pause_until)
    )
    db.commit()


def _retry_at(error_detail: dict) -> datetime:
    retry_after = error_detail.get("retry_after_seconds")
    delay_seconds = retry_after if isinstance(retry_after, int) and retry_after > 0 else 60
    return datetime.now(UTC) + timedelta(seconds=delay_seconds)
