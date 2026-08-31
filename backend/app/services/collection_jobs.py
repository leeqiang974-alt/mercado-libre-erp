import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.collection_job import CollectionJob, CollectionJobStatus
from app.models.source_product import SourceProduct, SourceProductStatus
from app.schemas.collection_jobs import CollectionJobRead
from app.services.amazon.collector import CollectionResult
from app.services.amazon.throttle import record_domain_outcome, reserve_domain_request
from app.services.drafts import create_product_draft
from app.services.source_products import (
    create_source_product,
    selected_source_variant,
    to_source_product_summary,
)
from app.services.audit_events import create_audit_event

Collector = Callable[[str, str], Awaitable[CollectionResult]]


def create_collection_job(db: Session, source_url: str, target_site_id: str, *, campaign_id: int | None = None, campaign_keyword: str | None = None) -> CollectionJob:
    return create_collection_jobs(db, [(source_url, target_site_id)], campaign_id=campaign_id, campaign_keyword=campaign_keyword)[0]


def create_collection_jobs(
    db: Session, entries: list[tuple[str, str]], *, campaign_id: int | None = None, campaign_keyword: str | None = None
) -> list[CollectionJob]:
    jobs = [
        CollectionJob(
            source_url=source_url,
            source_identity=source_url,
            target_site_id=target_site_id,
            campaign_id=campaign_id,
            campaign_keyword=campaign_keyword,
        )
        for source_url, target_site_id in entries
    ]
    db.add_all(jobs)
    db.flush()
    for job in jobs:
        create_audit_event(
            db,
            actor_type="system",
            actor_id="collection-api",
            action="collection_job.created",
            entity_type="collection_job",
            entity_id=str(job.id),
            after={
                "status": CollectionJobStatus.PENDING.value,
                "source_url": job.source_url,
                "target_site_id": job.target_site_id,
                "campaign_id": job.campaign_id,
                "campaign_keyword": job.campaign_keyword,
            },
            commit=False,
        )
    db.commit()
    for job in jobs:
        db.refresh(job)
    return jobs


def list_collection_jobs(
    db: Session, *, limit: int = 100, offset: int = 0, campaign_id: int | None = None, status: str | None = None
) -> list[CollectionJobRead]:
    query = db.query(CollectionJob)
    if campaign_id is not None:
        query = query.filter(CollectionJob.campaign_id == campaign_id)
    if status is not None:
        query = query.filter(CollectionJob.status == status)
    rows = (
        query
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
        before = {"status": job.status.value, "started_at": job.started_at.isoformat() if job.started_at else None}
        job.status = CollectionJobStatus.FAILED
        job.message = "Collection worker interrupted; retry is safe."
        job.completed_at = datetime.now(UTC)
        job.claimed_by = None
        job.claimed_at = None
        create_audit_event(
            db,
            actor_type="system",
            actor_id="collection-recovery",
            action="collection_job.stale_recovered",
            entity_type="collection_job",
            entity_id=str(job.id),
            before=before,
            after={"status": job.status.value, "message": job.message},
            commit=False,
        )
    if jobs:
        db.commit()
    return len(jobs)


async def run_collection_job(
    db: Session,
    job_id: int,
    collector: Collector,
    timeout_seconds: float | None = None,
    domain_min_interval_seconds: int | None = None,
    domain_request_lease_seconds: int = 900,
    challenge_backoff_base_seconds: int = 300,
    challenge_backoff_max_seconds: int = 21600,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
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

    current_time = now()
    if job.next_attempt_at is not None and _utc(job.next_attempt_at) > _utc(current_time):
        db.commit()
        db.refresh(job)
        return job
    reservation_id: str | None = None
    if domain_min_interval_seconds is not None:
        reservation = reserve_domain_request(
            db,
            job.source_url,
            now=current_time,
            min_interval_seconds=domain_min_interval_seconds,
            lease_seconds=domain_request_lease_seconds,
        )
        if not reservation.reserved:
            job.status = CollectionJobStatus.PENDING
            job.started_at = None
            job.completed_at = None
            job.next_attempt_at = reservation.available_at
            job.message = (
                f"Deferred by Amazon domain throttle until "
                f"{reservation.available_at.isoformat()}."
            )
            db.commit()
            db.refresh(job)
            return job
        reservation_id = reservation.reservation_id

    job.status = CollectionJobStatus.RUNNING
    job.message = ""
    job.started_at = current_time
    job.completed_at = None
    job.next_attempt_at = None
    job.claimed_by = None
    job.claimed_at = None
    create_audit_event(
        db,
        actor_type="system",
        actor_id="collection-worker",
        action="collection_job.started",
        entity_type="collection_job",
        entity_id=str(job.id),
        before={"status": CollectionJobStatus.PENDING.value},
        after={"status": CollectionJobStatus.RUNNING.value, "source_url": job.source_url},
        commit=False,
    )
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
        job.claimed_by = None
        job.claimed_at = None
        create_audit_event(
            db,
            actor_type="system",
            actor_id="collection-worker",
            action="collection_job.finished",
            entity_type="collection_job",
            entity_id=str(job.id),
            before={"status": CollectionJobStatus.RUNNING.value},
            after={"status": job.status.value, "message": message},
            commit=False,
        )
        _finish_domain_reservation(
            db,
            job.source_url,
            reservation_id,
            "failed",
            now(),
            domain_min_interval_seconds,
            challenge_backoff_base_seconds,
            challenge_backoff_max_seconds,
        )
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
        job.claimed_by = None
        job.claimed_at = None
        create_audit_event(
            db,
            actor_type="system",
            actor_id="collection-worker",
            action="collection_job.finished",
            entity_type="collection_job",
            entity_id=str(job.id),
            before={"status": CollectionJobStatus.RUNNING.value},
            after={"status": job.status.value, "message": message},
            commit=False,
        )
        _finish_domain_reservation(
            db,
            job.source_url,
            reservation_id,
            "failed",
            now(),
            domain_min_interval_seconds,
            challenge_backoff_base_seconds,
            challenge_backoff_max_seconds,
        )
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
            collection_method=result.collection_method,
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
        job.claimed_by = None
        job.claimed_at = None
        create_audit_event(
            db,
            actor_type="system",
            actor_id="collection-worker",
            action="collection_job.finished",
            entity_type="collection_job",
            entity_id=str(job.id),
            before={"status": CollectionJobStatus.RUNNING.value},
            after={
                "status": job.status.value,
                "draft_id": job.draft_id,
                "source_product_id": job.source_product_id,
                "collection_method": result.collection_method,
            },
            commit=False,
        )
        _finish_domain_reservation(
            db,
            job.source_url,
            reservation_id,
            (
                "challenge"
                if result.status.value == "needs_manual_action"
                and result.message.startswith("Amazon challenge detected")
                else result.status.value
            ),
            now(),
            domain_min_interval_seconds,
            challenge_backoff_base_seconds,
            challenge_backoff_max_seconds,
        )
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
        job.claimed_by = None
        job.claimed_at = None
        create_audit_event(
            db,
            actor_type="system",
            actor_id="collection-worker",
            action="collection_job.persistence_failed",
            entity_type="collection_job",
            entity_id=str(job.id),
            after={"status": job.status.value, "message": job.message},
            commit=False,
        )
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
        campaign_id=job.campaign_id,
        campaign_keyword=job.campaign_keyword,
        source_product_id=job.source_product_id,
        draft_id=job.draft_id,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        next_attempt_at=(
            _utc(job.next_attempt_at) if job.next_attempt_at is not None else None
        ),
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


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _finish_domain_reservation(
    db: Session,
    source_url: str,
    reservation_id: str | None,
    outcome: str,
    finished_at: datetime,
    min_interval_seconds: int | None,
    challenge_backoff_base_seconds: int,
    challenge_backoff_max_seconds: int,
) -> None:
    if reservation_id is None or min_interval_seconds is None:
        return
    record_domain_outcome(
        db,
        source_url,
        outcome=outcome,
        now=finished_at,
        challenge_backoff_base_seconds=challenge_backoff_base_seconds,
        challenge_backoff_max_seconds=challenge_backoff_max_seconds,
        min_interval_seconds=min_interval_seconds,
        reservation_id=reservation_id,
    )
