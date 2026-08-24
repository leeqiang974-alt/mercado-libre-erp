from fastapi import HTTPException
from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.core.config import get_settings
from app.models.collection_job import CollectionJob, CollectionJobStatus
from app.services.amazon.collector import CollectionResult, collect_amazon_page
from app.services.collection_jobs import (
    Collector,
    recover_stale_collection_jobs,
    run_collection_job,
)
from app.services.amazon.keyword_campaigns import run_one_keyword_campaign_step


WorkerSummary = dict[str, int]


async def run_pending_collection_jobs(
    db: Session,
    limit: int = 10,
    collector: Collector = collect_amazon_page,
) -> WorkerSummary:
    campaign_summary = await run_one_keyword_campaign_step(db)
    recovered = recover_stale_collection_jobs(db, get_settings().job_stale_after_seconds)
    settings = get_settings()
    now = datetime.now(UTC)
    jobs = db.scalars(
        select(CollectionJob)
        .where(
            CollectionJob.status == CollectionJobStatus.PENDING,
            or_(
                CollectionJob.next_attempt_at.is_(None),
                CollectionJob.next_attempt_at <= now,
            ),
        )
        .order_by(CollectionJob.id)
        .limit(limit)
    ).all()
    summary = {
        "processed": 0,
        "completed": 0,
        "needs_manual_action": 0,
        "failed": 0,
        "deferred": 0,
        "recovered": recovered,
        "campaigns": campaign_summary["campaigns"],
        "campaign_queued": campaign_summary["queued"],
    }
    for job in jobs:
        try:
            result = await run_collection_job(
                db=db,
                job_id=job.id,
                collector=collector,
                timeout_seconds=get_settings().job_execution_timeout_seconds,
                domain_min_interval_seconds=settings.amazon_domain_min_interval_seconds,
                domain_request_lease_seconds=settings.job_stale_after_seconds,
                challenge_backoff_base_seconds=(
                    settings.amazon_challenge_backoff_base_seconds
                ),
                challenge_backoff_max_seconds=(
                    settings.amazon_challenge_backoff_max_seconds
                ),
            )
        except HTTPException as exc:
            if exc.status_code not in {404, 409}:
                raise
            db.rollback()
            continue
        except StaleDataError:
            db.rollback()
            continue
        summary["processed"] += 1
        if result.status == CollectionJobStatus.COMPLETED:
            summary["completed"] += 1
        elif result.status == CollectionJobStatus.NEEDS_MANUAL_ACTION:
            summary["needs_manual_action"] += 1
        elif result.status == CollectionJobStatus.FAILED:
            summary["failed"] += 1
        elif result.status == CollectionJobStatus.PENDING:
            summary["deferred"] += 1
    return summary


def summarize_collection_result(result: CollectionResult) -> str:
    return f"{result.status.value}: {result.message}"
