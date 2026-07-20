import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.collection_job import CollectionJob, CollectionJobStatus
from app.models.source_product import SourceProductStatus
from app.schemas.collection_jobs import CollectionJobRead
from app.services.amazon.collector import CollectionResult
from app.services.drafts import create_product_draft
from app.services.source_products import create_source_product

Collector = Callable[[str, str], Awaitable[CollectionResult]]


def create_collection_job(db: Session, source_url: str, target_site_id: str) -> CollectionJob:
    job = CollectionJob(source_url=source_url, target_site_id=target_site_id)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def list_collection_jobs(db: Session) -> list[CollectionJobRead]:
    rows = db.query(CollectionJob).order_by(CollectionJob.id.desc()).all()
    return [to_collection_job_read(row) for row in rows]


def recover_stale_collection_jobs(db: Session, stale_after_seconds: int) -> int:
    cutoff = datetime.now(UTC) - timedelta(seconds=stale_after_seconds)
    jobs = (
        db.query(CollectionJob)
        .filter(
            CollectionJob.status == CollectionJobStatus.RUNNING,
            CollectionJob.started_at.is_not(None),
            CollectionJob.started_at < cutoff,
        )
        .all()
    )
    for job in jobs:
        job.status = CollectionJobStatus.FAILED
        job.message = "Collection worker interrupted; retry is safe."
        job.completed_at = datetime.now(UTC)
    if jobs:
        db.commit()
    return len(jobs)


async def run_collection_job(
    db: Session,
    job_id: int,
    collector: Collector,
    timeout_seconds: float | None = None,
) -> CollectionJob:
    job = (
        db.query(CollectionJob)
        .filter(CollectionJob.id == job_id)
        .with_for_update()
        .populate_existing()
        .one_or_none()
    )
    if job is None:
        raise HTTPException(status_code=404, detail="Collection job not found.")
    if job.status == CollectionJobStatus.COMPLETED:
        return job
    if job.status == CollectionJobStatus.RUNNING:
        raise HTTPException(status_code=409, detail="Collection job is already running.")

    job.status = CollectionJobStatus.RUNNING
    job.message = ""
    job.started_at = datetime.now(UTC)
    job.completed_at = None
    db.commit()

    try:
        collection = collector(job.source_url, job.target_site_id)
        result = (
            await asyncio.wait_for(collection, timeout=timeout_seconds)
            if timeout_seconds is not None
            else await collection
        )
    except TimeoutError:
        message = "Collection timed out; retry is safe."
        source = create_source_product(
            db,
            source_url=job.source_url,
            status=SourceProductStatus.FAILED,
            collection_error=message,
        )
        job.source_product_id = source.id
        job.draft_id = None
        job.message = message
        job.completed_at = datetime.now(UTC)
        job.status = CollectionJobStatus.FAILED
        db.commit()
        db.refresh(job)
        return job
    except Exception as exc:
        message = f"Collection failed: {exc}"
        source = create_source_product(
            db,
            source_url=job.source_url,
            status=SourceProductStatus.FAILED,
            collection_error=message,
        )
        job.source_product_id = source.id
        job.draft_id = None
        job.message = message
        job.completed_at = datetime.now(UTC)
        job.status = CollectionJobStatus.FAILED
        db.commit()
        db.refresh(job)
        return job

    status_map = {
        "collected": SourceProductStatus.COLLECTED,
        "needs_manual_action": SourceProductStatus.NEEDS_MANUAL_ACTION,
        "failed": SourceProductStatus.FAILED,
    }
    source = create_source_product(
        db,
        source_url=job.source_url,
        status=status_map[result.status.value],
        collection_error="" if result.status.value == "collected" else result.message,
    )
    draft = None
    if result.draft is not None:
        draft = create_product_draft(db, result.draft, source_product_id=source.id)

    job.source_product_id = source.id
    job.draft_id = draft.id if draft else None
    job.message = result.message
    job.completed_at = datetime.now(UTC)
    job.status = _job_status_from_result(result)
    db.commit()
    db.refresh(job)
    return job


def to_collection_job_read(job: CollectionJob) -> CollectionJobRead:
    return CollectionJobRead(
        id=job.id,
        source_url=job.source_url,
        target_site_id=job.target_site_id,
        status=job.status.value,
        message=job.message,
        source_product_id=job.source_product_id,
        draft_id=job.draft_id,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )


def _job_status_from_result(result: CollectionResult) -> CollectionJobStatus:
    if result.status.value == "collected":
        return CollectionJobStatus.COMPLETED
    if result.status.value == "needs_manual_action":
        return CollectionJobStatus.NEEDS_MANUAL_ACTION
    return CollectionJobStatus.FAILED
