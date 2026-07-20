import asyncio
from concurrent.futures import ThreadPoolExecutor
import os
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.collection_job import CollectionJob
from app.models.source_product import SourceProduct
from app.services.amazon.collector import CollectionResult, CollectionStatus
from app.workers import collection_worker


POSTGRES_URL = os.getenv("TEST_POSTGRES_URL", "")


@pytest.mark.skipif(not POSTGRES_URL, reason="TEST_POSTGRES_URL is not configured")
def test_two_postgres_workers_skip_a_lost_collection_job_claim(monkeypatch):
    engine = create_engine(POSTGRES_URL, pool_pre_ping=True)
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    source_url = f"https://www.amazon.com/dp/B000TEST01?claim_test={uuid4().hex}"
    with testing_session() as db:
        job = CollectionJob(source_url=source_url, target_site_id="MLM")
        db.add(job)
        db.commit()
        job_id = job.id

    original = collection_worker.run_collection_job
    both_batches_selected = Barrier(2)

    async def synchronized_claim(**kwargs):
        both_batches_selected.wait(timeout=10)
        return await original(**kwargs)

    async def collector(source_url: str, target_site_id: str) -> CollectionResult:
        await asyncio.sleep(0.2)
        return CollectionResult(
            status=CollectionStatus.NEEDS_MANUAL_ACTION,
            source_url=source_url,
            message="claim test",
        )

    monkeypatch.setattr(collection_worker, "run_collection_job", synchronized_claim)

    def run_worker():
        with testing_session() as db:
            return asyncio.run(
                collection_worker.run_pending_collection_jobs(
                    db,
                    limit=1,
                    collector=collector,
                )
            )

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            summaries = list(pool.map(lambda _: run_worker(), range(2)))

        assert sorted(summary["processed"] for summary in summaries) == [0, 1]
        assert sum(summary["needs_manual_action"] for summary in summaries) == 1
    finally:
        with testing_session() as db:
            job = db.get(CollectionJob, job_id)
            if job:
                db.delete(job)
                db.flush()
            for source in db.query(SourceProduct).filter(SourceProduct.source_url == source_url):
                db.delete(source)
            db.commit()
        engine.dispose()
