import pytest
from datetime import UTC, datetime, timedelta
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm.exc import StaleDataError

from app.db.base import Base
from app.models.collection_job import CollectionJob, CollectionJobStatus
from app.models.product_draft import ProductDraft
from app.models.registry import import_all_models
from app.models.source_product import SourceProduct
from app.schemas.drafts import ProductDraftCreate
from app.services.amazon.collector import CollectionResult, CollectionStatus
from app.workers.collection_worker import run_pending_collection_jobs
from app.workers import collection_worker


def make_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    import_all_models()
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return testing_session


@pytest.mark.asyncio
async def test_worker_runs_pending_collection_jobs_up_to_limit():
    testing_session = make_session()
    with testing_session() as db:
        db.add(CollectionJob(source_url="https://amazon.example/a", target_site_id="MLM"))
        db.add(CollectionJob(source_url="https://amazon.example/b", target_site_id="MLM"))
        db.add(CollectionJob(source_url="https://amazon.example/c", target_site_id="MLM"))
        db.commit()

    async def fake_collector(source_url: str, target_site_id: str):
        return CollectionResult(
            status=CollectionStatus.COLLECTED,
            source_url=source_url,
            message="collected",
            draft=ProductDraftCreate(
                title=f"Draft {source_url[-1]}",
                target_site_id=target_site_id,
                target_category_id="MLM123",
                price=10.0,
                currency="USD",
                stock=1,
                image_urls=["https://example.com/a.jpg"],
            ),
        )

    with testing_session() as db:
        summary = await run_pending_collection_jobs(db, limit=2, collector=fake_collector)

    assert summary == {
        "processed": 2,
        "completed": 2,
        "needs_manual_action": 0,
        "failed": 0,
        "deferred": 0,
        "recovered": 0,
    }
    with testing_session() as db:
        jobs = db.query(CollectionJob).order_by(CollectionJob.id).all()
        assert [job.status for job in jobs] == [
            CollectionJobStatus.COMPLETED,
            CollectionJobStatus.COMPLETED,
            CollectionJobStatus.PENDING,
        ]
        assert db.query(SourceProduct).count() == 2
        assert db.query(ProductDraft).count() == 2


@pytest.mark.asyncio
async def test_worker_skips_non_pending_collection_jobs():
    testing_session = make_session()
    with testing_session() as db:
        db.add(
            CollectionJob(
                source_url="https://amazon.example/done",
                target_site_id="MLM",
                status=CollectionJobStatus.COMPLETED,
            )
        )
        db.commit()

    async def fake_collector(source_url: str, target_site_id: str):
        raise AssertionError("collector should not run")

    with testing_session() as db:
        summary = await run_pending_collection_jobs(db, limit=10, collector=fake_collector)

    assert summary == {
        "processed": 0,
        "completed": 0,
        "needs_manual_action": 0,
        "failed": 0,
        "deferred": 0,
        "recovered": 0,
    }


@pytest.mark.asyncio
async def test_worker_skips_job_claimed_by_another_worker(monkeypatch):
    testing_session = make_session()
    with testing_session() as db:
        db.add(CollectionJob(source_url="https://amazon.example/race", target_site_id="MLM"))
        db.commit()

    async def lost_claim(**kwargs):
        raise HTTPException(status_code=409, detail="claimed")

    monkeypatch.setattr(collection_worker, "run_collection_job", lost_claim)
    with testing_session() as db:
        summary = await run_pending_collection_jobs(db)

    assert summary["processed"] == 0
    assert summary["failed"] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "lost_claim",
    [
        HTTPException(status_code=404, detail="deleted"),
        StaleDataError("row disappeared"),
    ],
)
async def test_worker_skips_job_removed_after_candidate_selection(monkeypatch, lost_claim):
    testing_session = make_session()
    with testing_session() as db:
        db.add(CollectionJob(source_url="https://amazon.example/removed", target_site_id="MLM"))
        db.commit()

    async def removed_job(**kwargs):
        raise lost_claim

    monkeypatch.setattr(collection_worker, "run_collection_job", removed_job)
    with testing_session() as db:
        summary = await run_pending_collection_jobs(db)

    assert summary == {
        "processed": 0,
        "completed": 0,
        "needs_manual_action": 0,
        "failed": 0,
        "deferred": 0,
        "recovered": 0,
    }


@pytest.mark.asyncio
async def test_worker_defers_second_job_for_same_amazon_domain(monkeypatch):
    testing_session = make_session()
    with testing_session() as db:
        db.add_all(
            [
                CollectionJob(
                    source_url="https://amazon.com/dp/B000TEST01",
                    target_site_id="MLM",
                ),
                CollectionJob(
                    source_url="https://amazon.com/dp/B000TEST02",
                    target_site_id="MLM",
                ),
            ]
        )
        db.commit()

    calls: list[str] = []

    async def fake_collector(source_url: str, target_site_id: str):
        calls.append(source_url)
        return CollectionResult(
            status=CollectionStatus.FAILED,
            source_url=source_url,
            message="temporary failure",
        )

    monkeypatch.setattr(
        collection_worker.get_settings(), "amazon_domain_min_interval_seconds", 8
    )
    with testing_session() as db:
        summary = await run_pending_collection_jobs(db, collector=fake_collector)

    assert len(calls) == 1
    assert summary["processed"] == 2
    assert summary["failed"] == 1
    assert summary["deferred"] == 1
    with testing_session() as db:
        jobs = db.query(CollectionJob).order_by(CollectionJob.id).all()
        assert jobs[1].status == CollectionJobStatus.PENDING
        assert jobs[1].next_attempt_at is not None
        assert jobs[1].message.startswith("Deferred by Amazon domain throttle")


@pytest.mark.asyncio
async def test_worker_skips_pending_job_until_scheduled_time():
    testing_session = make_session()
    with testing_session() as db:
        db.add(
            CollectionJob(
                source_url="https://amazon.com/dp/B000TEST01",
                target_site_id="MLM",
                next_attempt_at=datetime.now(UTC) + timedelta(hours=1),
            )
        )
        db.commit()

    async def unexpected_collector(source_url: str, target_site_id: str):
        raise AssertionError("scheduled job must not run early")

    with testing_session() as db:
        summary = await run_pending_collection_jobs(db, collector=unexpected_collector)

    assert summary["processed"] == 0
    assert summary["deferred"] == 0


@pytest.mark.asyncio
async def test_failed_retry_returns_to_pending_when_domain_is_throttled():
    testing_session = make_session()
    with testing_session() as db:
        db.add_all(
            [
                CollectionJob(
                    source_url="https://amazon.com/dp/B000TEST01",
                    target_site_id="MLM",
                ),
                CollectionJob(
                    source_url="https://amazon.com/dp/B000TEST02",
                    target_site_id="MLM",
                    status=CollectionJobStatus.FAILED,
                    started_at=datetime.now(UTC) - timedelta(minutes=1),
                    completed_at=datetime.now(UTC),
                ),
            ]
        )
        db.commit()
        first_id, retry_id = [job.id for job in db.query(CollectionJob).order_by(CollectionJob.id)]

    async def failed_collector(source_url: str, target_site_id: str):
        return CollectionResult(
            status=CollectionStatus.FAILED,
            source_url=source_url,
            message="temporary failure",
        )

    with testing_session() as db:
        await collection_worker.run_collection_job(
            db=db,
            job_id=first_id,
            collector=failed_collector,
            domain_min_interval_seconds=30,
        )
        retry = await collection_worker.run_collection_job(
            db=db,
            job_id=retry_id,
            collector=failed_collector,
            domain_min_interval_seconds=30,
        )

    assert retry.status == CollectionJobStatus.PENDING
    assert retry.started_at is None
    assert retry.completed_at is None
    assert retry.next_attempt_at is not None


@pytest.mark.asyncio
async def test_worker_recovers_stale_running_collection_job():
    testing_session = make_session()
    with testing_session() as db:
        db.add(
            CollectionJob(
                source_url="https://www.amazon.com/dp/B000TEST01",
                target_site_id="MLM",
                status=CollectionJobStatus.RUNNING,
                started_at=datetime.now(UTC) - timedelta(hours=1),
            )
        )
        db.commit()

    async def unexpected_collector(source_url: str, target_site_id: str):
        raise AssertionError("recovered jobs must require an explicit retry")

    with testing_session() as db:
        summary = await run_pending_collection_jobs(db, collector=unexpected_collector)

    assert summary["recovered"] == 1
    assert summary["processed"] == 0
    with testing_session() as db:
        job = db.query(CollectionJob).one()
        assert job.status == CollectionJobStatus.FAILED
        assert job.message == "Collection worker interrupted; retry is safe."
