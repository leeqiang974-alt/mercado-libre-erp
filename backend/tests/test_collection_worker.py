import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.collection_job import CollectionJob, CollectionJobStatus
from app.models.product_draft import ProductDraft
from app.models.registry import import_all_models
from app.models.source_product import SourceProduct
from app.schemas.drafts import ProductDraftCreate
from app.services.amazon.collector import CollectionResult, CollectionStatus
from app.workers.collection_worker import run_pending_collection_jobs


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

    assert summary == {"processed": 2, "completed": 2, "needs_manual_action": 0, "failed": 0}
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

    assert summary == {"processed": 0, "completed": 0, "needs_manual_action": 0, "failed": 0}
