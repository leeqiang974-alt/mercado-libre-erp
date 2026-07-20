from fastapi import HTTPException
from sqlalchemy import select
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


WorkerSummary = dict[str, int]


async def run_pending_collection_jobs(
    db: Session,
    limit: int = 10,
    collector: Collector = collect_amazon_page,
) -> WorkerSummary:
    recovered = recover_stale_collection_jobs(db, get_settings().job_stale_after_seconds)
    jobs = db.scalars(
        select(CollectionJob)
        .where(CollectionJob.status == CollectionJobStatus.PENDING)
        .order_by(CollectionJob.id)
        .limit(limit)
    ).all()
    summary = {
        "processed": 0,
        "completed": 0,
        "needs_manual_action": 0,
        "failed": 0,
        "recovered": recovered,
    }
    for job in jobs:
        try:
            result = await run_collection_job(
                db=db,
                job_id=job.id,
                collector=collector,
                timeout_seconds=get_settings().job_execution_timeout_seconds,
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
    return summary


def summarize_collection_result(result: CollectionResult) -> str:
    return f"{result.status.value}: {result.message}"
