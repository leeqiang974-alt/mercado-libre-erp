import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.collection_job import CollectionJob, CollectionJobStatus
from app.models.source_product import SourceProduct, SourceProductStatus
from app.schemas.collection_jobs import CollectionJobRead
from app.services.amazon.collector import CollectionResult
from app.services.drafts import create_product_draft
from app.services.source_products import (
    create_source_product,
    selected_source_variant,
    to_source_product_summary,
)

Collector = Callable[[str, str], Awaitable[CollectionResult]]


def create_collection_job(db: Session, source_url: str, target_site_id: str) -> CollectionJob:
    return create_collection_jobs(db, [(source_url, target_site_id)])[0]


def create_collection_jobs(
    db: Session, entries: list[tuple[str, str]]
) -> list[CollectionJob]:
    jobs = [
        CollectionJob(
            source_url=source_url,
            source_identity=source_url,
            target_site_id=target_site_id,
        )
        for source_url, target_site_id in entries
    ]
    db.add_all(jobs)
    db.commit()
    for job in jobs:
        db.refresh(job)
    return jobs


def list_collection_jobs(
    db: Session, *, limit: int = 100, offset: int = 0
) -> list[CollectionJobRead]:
    rows = (
        db.query(CollectionJob)
        .order_by(CollectionJob.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    source_ids = {row.source_product_id for row in rows if row.source_product_id is not None}
    sources = (
        {
            source.id: source
            for source in db.query(SourceProduct).filter(SourceProduct.id.in_(source_ids)).all()
        }
        if source_ids
        else {}
    )
    return [
        to_collection_job_read(row, sources.get(row.source_product_id))
        for row in rows
    ]


def list_collection_jobs_by_ids(
    db: Session, job_ids: list[int]
) -> list[CollectionJobRead]:
    if not job_ids:
        return []
    rows = (
        db.query(CollectionJob)
        .filter(CollectionJob.id.in_(job_ids))
        .order_by(CollectionJob.id.desc())
        .all()
    )
    source_ids = {row.source_product_id for row in rows if row.source_product_id is not None}
    sources = (
        {
            source.id: source
            for source in db.query(SourceProduct).filter(SourceProduct.id.in_(source_ids)).all()
        }
        if source_ids
        else {}
    )
    return [
        to_collection_job_read(row, sources.get(row.source_product_id))
        for row in rows
    ]


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

    try:
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
            snapshot=result.source_snapshot,
            collection_method="browser_page",
        )
        draft = None
        if result.draft is not None:
            variant_asin, variant_attributes = selected_source_variant(
                result.source_snapshot, source.asin
            )
            draft = create_product_draft(
                db,
                result.draft,
                source_product_id=source.id,
                source_variant_asin=variant_asin,
                source_variant_attributes=variant_attributes,
                commit=False,
            )

        job.source_product_id = source.id
        job.draft_id = draft.id if draft else None
        job.message = result.message
        job.completed_at = datetime.now(UTC)
        job.status = _job_status_from_result(result)
        db.commit()
    except Exception as exc:
        db.rollback()
        job = db.get(CollectionJob, job_id)
        if job is None:
            raise
        job.source_product_id = None
        job.draft_id = None
        job.message = f"Collection persistence failed: {exc}"
        job.completed_at = datetime.now(UTC)
        job.status = CollectionJobStatus.FAILED
        db.commit()
    db.refresh(job)
    return job


def to_collection_job_read(
    job: CollectionJob,
    source_product: SourceProduct | None = None,
) -> CollectionJobRead:
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
        source_product=(
            to_source_product_summary(source_product) if source_product is not None else None
        ),
    )


def _job_status_from_result(result: CollectionResult) -> CollectionJobStatus:
    if result.status.value == "collected":
        return CollectionJobStatus.COMPLETED
    if result.status.value == "needs_manual_action":
        return CollectionJobStatus.NEEDS_MANUAL_ACTION
    return CollectionJobStatus.FAILED
