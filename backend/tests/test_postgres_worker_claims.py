import asyncio
from concurrent.futures import ThreadPoolExecutor
import os
from threading import Barrier
import time
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.collection_job import CollectionJob
from app.models.draft_listing_config import DraftListingConfig
from app.models.draft_pricing_config import DraftPricingConfig
from app.models.meli_metadata_cache import MeliMetadataCache
from app.models.source_product import SourceProduct, SourceProductStatus
from app.models.product_draft import ProductDraft
from app.models.publish_job import PublishJob
from app.models.review_result import ReviewDecision, ReviewResult
from app.models.store import Store
from app.api.routes.imports import AmazonUrlImport, create_amazon_url_collection_job
from app.services.amazon.collector import CollectionResult, CollectionStatus
from app.schemas.drafts import ProductDraftCreate
from app.schemas.publishing import ListingChoice
from app.schemas.reviews import ReviewResponse
from app.services.publish_jobs import create_publish_job
from app.services.drafts import update_draft_content
from app.services.draft_listing_configs import build_configured_draft
from app.workers import collection_worker
from app.services import source_products as source_products_service


POSTGRES_URL = os.getenv("TEST_POSTGRES_URL", "")


@pytest.mark.skipif(not POSTGRES_URL, reason="TEST_POSTGRES_URL is not configured")
def test_final_publish_evidence_lock_blocks_concurrent_draft_change():
    engine = create_engine(POSTGRES_URL, pool_pre_ping=True)
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    marker = uuid4().hex
    category_id = f"MLM{marker[:8].upper()}"
    with testing_session() as db:
        draft = ProductDraft(
            title=f"Publish lock {marker}",
            target_site_id="MLM",
            target_category_id=category_id,
            source_price=10,
            source_currency="USD",
            price=180,
            currency="MXN",
            stock=1,
            image_urls_json=["https://example.com/a.jpg"],
        )
        db.add(draft)
        db.flush()
        draft_id = draft.id
        db.add_all(
            [
                MeliMetadataCache(
                    cache_key=f"category_attributes:{category_id}",
                    payload_json={"attributes": [], "verified": True},
                ),
                DraftListingConfig(
                    product_draft_id=draft_id,
                    site_id="MLM",
                    category_id=category_id,
                    listing_type_id="gold_special",
                    fulfillment="not_full",
                    attributes_json=[],
                ),
                DraftPricingConfig(
                    product_draft_id=draft_id,
                    source_price=10,
                    source_currency="USD",
                    target_currency="MXN",
                    exchange_rate=18,
                    purchase_extra_cost=0,
                    shipping_cost=0,
                    platform_fee_rate=0,
                    tax_rate=0,
                    profit_margin_rate=0,
                    rounding_increment=0.01,
                    landed_cost=180,
                    target_price=180,
                ),
            ]
        )
        db.commit()

    try:
        with testing_session() as locked_db:
            assert locked_db.get(ProductDraft, draft_id).title == f"Publish lock {marker}"
            with testing_session() as concurrent_db:
                update_draft_content(
                    concurrent_db, draft_id, title=f"Changed before lock {marker}"
                )
                concurrent_db.commit()
            locked_draft, _ = build_configured_draft(
                locked_db, draft_id, lock_draft=True
            )
            assert locked_draft.title == f"Changed before lock {marker}"

            def change_draft():
                with testing_session() as db:
                    update_draft_content(db, draft_id, title=f"Changed {marker}")
                    db.commit()

            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(change_draft)
                time.sleep(0.2)
                assert not future.done(), "concurrent edit bypassed final publish evidence lock"
                locked_db.commit()
                future.result(timeout=5)
        with testing_session() as db:
            assert db.get(ProductDraft, draft_id).title == f"Changed {marker}"
    finally:
        with testing_session() as db:
            db.query(DraftPricingConfig).filter(
                DraftPricingConfig.product_draft_id == draft_id
            ).delete()
            db.query(DraftListingConfig).filter(
                DraftListingConfig.product_draft_id == draft_id
            ).delete()
            db.query(ProductDraft).filter(ProductDraft.id == draft_id).delete()
            db.query(MeliMetadataCache).filter(
                MeliMetadataCache.cache_key == f"category_attributes:{category_id}"
            ).delete()
            db.commit()
        engine.dispose()


@pytest.mark.skipif(not POSTGRES_URL, reason="TEST_POSTGRES_URL is not configured")
def test_postgres_concurrent_draft_changes_increment_every_version():
    engine = create_engine(POSTGRES_URL, pool_pre_ping=True)
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    marker = uuid4().hex
    with testing_session() as db:
        draft = ProductDraft(
            title=f"Version test {marker}",
            target_site_id="MLM",
            price=100,
            currency="MXN",
            stock=1,
        )
        db.add(draft)
        db.commit()
        db.refresh(draft)
        starting_version = draft.content_version
        review = ReviewResult(
            product_draft_id=draft.id,
            provider="claude+nvidia_behavioral_audit",
            prompt_version="meli-behavioral-audit-v4",
            risk_level="low",
            decision=ReviewDecision.PASS,
            reasons_json={"reason_codes": [], "reasons": []},
            suggested_changes_json={},
            draft_version=starting_version,
        )
        db.add(review)
        db.commit()
        draft_id = draft.id
        review_id = review.id

    both_updates_ready = Barrier(2)

    def change_draft(sequence: int):
        with testing_session() as db:
            both_updates_ready.wait(timeout=10)
            update_draft_content(db, draft_id, title=f"Version test {marker}-{sequence}")
            db.commit()

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(change_draft, range(2)))
        with testing_session() as db:
            current = db.get(ProductDraft, draft_id)
            persisted_review = db.get(ReviewResult, review_id)
            assert current.content_version == starting_version + 2
            assert current.risk_status == "unreviewed"
            assert persisted_review.draft_version != current.content_version
    finally:
        with testing_session() as db:
            db.query(ReviewResult).filter(ReviewResult.id == review_id).delete()
            db.query(ProductDraft).filter(ProductDraft.id == draft_id).delete()
            db.commit()
        engine.dispose()


@pytest.mark.skipif(not POSTGRES_URL, reason="TEST_POSTGRES_URL is not configured")
def test_two_postgres_requests_reuse_one_publish_job():
    engine = create_engine(POSTGRES_URL, pool_pre_ping=True)
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    marker = uuid4().hex
    with testing_session() as db:
        store = Store(
            site_id="MLM",
            seller_id=f"concurrent-{marker}",
            display_name="Concurrent test store",
            oauth_status="connected",
        )
        draft_row = ProductDraft(
            title=f"Concurrent {marker}",
            target_site_id="MLM",
            target_category_id="MLM123",
            price=100,
            currency="MXN",
            stock=1,
            image_urls_json=["https://example.com/a.jpg"],
        )
        db.add_all([store, draft_row])
        db.commit()
        db.refresh(store)
        db.refresh(draft_row)
        store_id = store.id
        draft_id = draft_row.id

    draft = ProductDraftCreate(
        title=f"Concurrent {marker}",
        target_site_id="MLM",
        target_category_id="MLM123",
        price=100,
        currency="MXN",
        stock=1,
        image_urls=["https://example.com/a.jpg"],
    )
    review = ReviewResponse(
        provider="claude+nvidia_behavioral_audit",
        decision="pass",
        risk_level="low",
        reason_codes=[],
        reasons=[],
    )
    listing_choice = ListingChoice(
        site_id="MLM",
        store_id=store_id,
        listing_type_id="gold_special",
        shipping_mode="me2",
        shipping_logistic_type="drop_off",
    )
    both_requests_ready = Barrier(2)

    def create_job():
        with testing_session() as db:
            both_requests_ready.wait(timeout=10)
            return create_publish_job(
                db=db,
                product_draft_id=draft_id,
                store_id=store_id,
                requested_by="operator",
                draft=draft,
                review=review,
                listing_choice=listing_choice,
            ).id

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            job_ids = list(pool.map(lambda _: create_job(), range(2)))
        assert job_ids[0] == job_ids[1]
        with testing_session() as db:
            assert db.query(PublishJob).filter(PublishJob.product_draft_id == draft_id).count() == 1
    finally:
        with testing_session() as db:
            db.query(PublishJob).filter(PublishJob.product_draft_id == draft_id).delete()
            db.query(ProductDraft).filter(ProductDraft.id == draft_id).delete()
            db.query(Store).filter(Store.id == store_id).delete()
            db.commit()
        engine.dispose()


@pytest.mark.skipif(not POSTGRES_URL, reason="TEST_POSTGRES_URL is not configured")
def test_two_postgres_requests_reuse_one_collection_job():
    engine = create_engine(POSTGRES_URL, pool_pre_ping=True)
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    asin = f"B{uuid4().hex[:9].upper()}"
    source_url = f"https://www.amazon.com/dp/{asin}"
    both_requests_ready = Barrier(2)

    def create_job():
        with testing_session() as db:
            both_requests_ready.wait(timeout=10)
            return create_amazon_url_collection_job(
                AmazonUrlImport(source_url=source_url, target_site_id="MLM"),
                db,
            ).id

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            job_ids = list(pool.map(lambda _: create_job(), range(2)))
        assert job_ids[0] == job_ids[1]
        with testing_session() as db:
            assert (
                db.query(CollectionJob)
                .filter(CollectionJob.source_url == f"https://amazon.com/dp/{asin}")
                .count()
                == 1
            )
    finally:
        with testing_session() as db:
            for job in db.query(CollectionJob).filter(CollectionJob.source_url.contains(asin)):
                db.delete(job)
            db.commit()
        engine.dispose()


@pytest.mark.skipif(not POSTGRES_URL, reason="TEST_POSTGRES_URL is not configured")
def test_two_postgres_requests_reuse_one_source_variant_draft(monkeypatch):
    engine = create_engine(POSTGRES_URL, pool_pre_ping=True)
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    asin = f"B{uuid4().hex[:9].upper()}"
    with testing_session() as db:
        source = SourceProduct(
            source_url=f"https://amazon.com/dp/{asin}",
            asin=asin,
            raw_status=SourceProductStatus.COLLECTED,
            title="Concurrent variant",
            source_price=15,
            source_currency="USD",
            variants_json=[
                {
                    "asin": asin,
                    "attributes": {"Color": "Black"},
                    "image_urls": [],
                    "selected": True,
                }
            ],
        )
        db.add(source)
        db.commit()
        source_id = source.id

    original_create = source_products_service.create_product_draft
    both_queries_finished = Barrier(2)

    def synchronized_create(*args, **kwargs):
        both_queries_finished.wait(timeout=10)
        return original_create(*args, **kwargs)

    monkeypatch.setattr(
        source_products_service, "create_product_draft", synchronized_create
    )

    def create_variant_draft():
        with testing_session() as db:
            source = db.get(SourceProduct, source_id)
            draft, _ = source_products_service.create_or_get_source_variant_draft(
                db, source, asin, "MLM"
            )
            return draft.id

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            draft_ids = list(pool.map(lambda _: create_variant_draft(), range(2)))
        assert draft_ids[0] == draft_ids[1]
        with testing_session() as db:
            assert (
                db.query(ProductDraft)
                .filter(
                    ProductDraft.source_product_id == source_id,
                    ProductDraft.source_variant_asin == asin,
                    ProductDraft.target_site_id == "MLM",
                )
                .count()
                == 1
            )
    finally:
        with testing_session() as db:
            db.query(ProductDraft).filter(
                ProductDraft.source_product_id == source_id
            ).delete()
            db.query(SourceProduct).filter(SourceProduct.id == source_id).delete()
            db.commit()
        engine.dispose()


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
