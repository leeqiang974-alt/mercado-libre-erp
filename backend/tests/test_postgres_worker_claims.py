import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from decimal import Decimal
import os
from threading import Barrier, Lock
import time
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import sessionmaker

from app.models.audit_event import AuditEvent
from app.models.amazon_domain_throttle import AmazonDomainThrottle
from app.models.collection_job import CollectionJob, CollectionJobStatus
from app.models.draft_listing_config import DraftListingConfig
from app.models.draft_pricing_config import DraftPricingConfig
from app.models.meli_metadata_cache import MeliMetadataCache
from app.models.source_product import SourceProduct, SourceProductStatus
from app.models.product_draft import ProductDraft
from app.models.provider_model_price import ProviderModelPrice
from app.models.publish_job import PublishJob
from app.models.review_result import ReviewDecision, ReviewResult
from app.models.review_job import ReviewJob, ReviewJobStatus
from app.models.store import Store
from app.models.token_credential import TokenCredential
from app.api.routes import imports as imports_route
from app.api.routes.imports import (
    AmazonHtmlImport,
    AmazonUrlImport,
    create_amazon_url_collection_job,
    import_amazon_html,
)
from app.services.amazon.collector import CollectionResult, CollectionStatus
from app.services.amazon.throttle import reserve_domain_request
from app.schemas.drafts import ProductDraftCreate
from app.schemas.publishing import ListingChoice
from app.schemas.reviews import ReviewResponse
from app.schemas.provider_pricing import ProviderModelPriceCreate
from app.services.publish_jobs import create_publish_job
from app.services.review_jobs import recover_stale_review_jobs
from app.services.drafts import update_draft_content
from app.services.provider_pricing import save_provider_model_price
from app.services.draft_listing_configs import build_configured_draft
from app.workers import collection_worker
from app.services import source_products as source_products_service
from app.services.meli.oauth import MercadoLibreToken
from app.services.meli.token_vault import (
    decrypt_token_value,
    encrypt_token_value,
    resolve_fresh_store_access_token,
)


POSTGRES_URL = os.getenv("TEST_POSTGRES_URL", "")


@pytest.mark.skipif(not POSTGRES_URL, reason="TEST_POSTGRES_URL is not configured")
def test_postgres_stale_review_recovery_is_claimed_once():
    engine = create_engine(POSTGRES_URL, pool_pre_ping=True)
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    marker = f"stale-review-{uuid4()}"
    ready = Barrier(2)

    with testing_session() as db:
        draft = ProductDraft(title=marker, content_version=1)
        db.add(draft)
        db.flush()
        job = ReviewJob(
            batch_id=str(uuid4()),
            product_draft_id=draft.id,
            requested_by="concurrency-test",
            draft_version=1,
            active_key=f"combined:{draft.id}",
            status=ReviewJobStatus.RUNNING,
            started_at=datetime.now(UTC) - timedelta(minutes=10),
        )
        db.add(job)
        db.commit()
        draft_id = draft.id
        job_id = job.id

    def recover_concurrently():
        with testing_session() as db:
            ready.wait(timeout=10)
            return recover_stale_review_jobs(db, stale_after_seconds=60)

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            recovered = list(pool.map(lambda _: recover_concurrently(), range(2)))
        assert sum(recovered) == 1
        with testing_session() as db:
            job = db.get(ReviewJob, job_id)
            assert job.status == ReviewJobStatus.FAILED
            assert db.query(AuditEvent).filter(
                AuditEvent.action == "review.job.finished",
                AuditEvent.entity_type == "review_job",
                AuditEvent.entity_id == str(job_id),
            ).count() == 1
    finally:
        with testing_session() as db:
            db.execute(delete(AuditEvent).where(AuditEvent.entity_id == str(job_id)))
            db.execute(delete(ReviewJob).where(ReviewJob.id == job_id))
            db.execute(delete(ProductDraft).where(ProductDraft.id == draft_id))
            db.commit()


@pytest.mark.skipif(not POSTGRES_URL, reason="TEST_POSTGRES_URL is not configured")
def test_postgres_serializes_amazon_domain_request_reservations():
    engine = create_engine(POSTGRES_URL, pool_pre_ping=True)
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    domain = "amazon.sg"
    url = f"https://{domain}/dp/B000TEST01"
    now = datetime.now(UTC)
    ready = Barrier(2)

    with testing_session() as db:
        db.execute(
            delete(AmazonDomainThrottle).where(AmazonDomainThrottle.domain == domain)
        )
        db.commit()

    def reserve_concurrently():
        with testing_session() as db:
            ready.wait(timeout=10)
            reservation = reserve_domain_request(
                db,
                url,
                now=now,
                min_interval_seconds=30,
                lease_seconds=30,
            )
            db.commit()
            return reservation

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            reservations = list(pool.map(lambda _: reserve_concurrently(), range(2)))
        assert sum(reservation.reserved for reservation in reservations) == 1
        deferred = next(
            reservation for reservation in reservations if not reservation.reserved
        )
        assert deferred.available_at == now + timedelta(seconds=30)
    finally:
        with testing_session() as db:
            db.execute(
                delete(AmazonDomainThrottle).where(AmazonDomainThrottle.domain == domain)
            )
            db.commit()


@pytest.mark.skipif(not POSTGRES_URL, reason="TEST_POSTGRES_URL is not configured")
def test_postgres_enforces_one_active_provider_model_price_during_concurrent_updates():
    engine = create_engine(POSTGRES_URL, pool_pre_ping=True)
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    model = f"concurrency-test-{uuid4().hex}"
    def payload(input_price: str) -> ProviderModelPriceCreate:
        return ProviderModelPriceCreate(
            provider="claude",
            model=model,
            currency="USD",
            input_price_per_million=Decimal(input_price),
            output_price_per_million=Decimal("15"),
        )
    with testing_session() as db:
        save_provider_model_price(db, payload("3"))
    ready = Barrier(2)

    def save_concurrently(input_price: str) -> str:
        with testing_session() as db:
            ready.wait(timeout=10)
            try:
                save_provider_model_price(db, payload(input_price))
                return "saved"
            except HTTPException as exc:
                assert exc.status_code == 409
                return "conflict"

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(save_concurrently, ["4", "5"]))
        assert "saved" in outcomes
        with testing_session() as db:
            rows = db.scalars(
                select(ProviderModelPrice)
                .where(
                    ProviderModelPrice.provider == "claude",
                    ProviderModelPrice.model == model,
                )
                .order_by(ProviderModelPrice.version)
            ).all()
            assert len({row.version for row in rows}) == len(rows)
            assert sum(row.active for row in rows) == 1
            assert max(row.version for row in rows if row.active) == max(
                row.version for row in rows
            )
    finally:
        with testing_session() as db:
            ids = [
                str(value)
                for value in db.scalars(
                    select(ProviderModelPrice.id).where(
                        ProviderModelPrice.provider == "claude",
                        ProviderModelPrice.model == model,
                    )
                )
            ]
            if ids:
                db.execute(
                    delete(AuditEvent).where(
                        AuditEvent.entity_type == "provider_model_price",
                        AuditEvent.entity_id.in_(ids),
                    )
                )
            db.execute(
                delete(ProviderModelPrice).where(
                    ProviderModelPrice.provider == "claude",
                    ProviderModelPrice.model == model,
                )
            )
            db.commit()
        engine.dispose()


@pytest.mark.skipif(not POSTGRES_URL, reason="TEST_POSTGRES_URL is not configured")
def test_postgres_serializes_manual_snapshot_job_resolution(monkeypatch):
    engine = create_engine(POSTGRES_URL, pool_pre_ping=True)
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    marker = uuid4().hex
    asin = f"B{marker[:9]}".upper()
    source_url = f"https://www.amazon.com/dp/{asin}"
    with testing_session() as db:
        job = CollectionJob(
            source_url=source_url,
            source_identity=source_url,
            target_site_id="MLM",
            status=CollectionJobStatus.NEEDS_MANUAL_ACTION,
            message="Amazon challenge detected",
        )
        db.add(job)
        db.commit()
        job_id = job.id

    original_validate = imports_route.validate_amazon_snapshot
    both_snapshots_validated = Barrier(2)

    def synchronized_validate(source_url: str, html: str):
        snapshot = original_validate(source_url, html)
        both_snapshots_validated.wait(timeout=10)
        return snapshot

    monkeypatch.setattr(imports_route, "validate_amazon_snapshot", synchronized_validate)
    payload = AmazonHtmlImport(
        source_url=source_url,
        html=(
            f"<input id='ASIN' value='{asin}' />"
            "<span id='productTitle'>Concurrent Snapshot</span>"
            "<span class='a-price'><span class='a-offscreen'>$9.99</span></span>"
            "<img id='landingImage' src='https://example.com/a.jpg' />"
        ),
        target_site_id="MLM",
        persist=True,
        collection_job_id=job_id,
    )

    def resolve_snapshot():
        with testing_session() as db:
            try:
                result = import_amazon_html(payload, db)
                return "completed", result.id
            except HTTPException as exc:
                db.rollback()
                return "rejected", exc.status_code, exc.detail

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: resolve_snapshot(), range(2)))
        assert sorted(result[0] for result in results) == ["completed", "rejected"]
        rejected = next(result for result in results if result[0] == "rejected")
        assert rejected[1:] == (409, "collection_job_not_waiting_for_snapshot")
        with testing_session() as db:
            job = db.get(CollectionJob, job_id)
            assert job.status == CollectionJobStatus.COMPLETED
            assert db.query(ProductDraft).filter_by(id=job.draft_id).count() == 1
            assert db.query(SourceProduct).filter_by(id=job.source_product_id).count() == 1
            assert (
                db.query(AuditEvent)
                .filter(
                    AuditEvent.action == "collection_job.snapshot_resolved",
                    AuditEvent.entity_id == str(job_id),
                )
                .count()
                == 1
            )
    finally:
        with testing_session() as db:
            job = db.get(CollectionJob, job_id)
            draft_id = job.draft_id if job else None
            source_product_id = job.source_product_id if job else None
            db.query(AuditEvent).filter(
                AuditEvent.action == "collection_job.snapshot_resolved",
                AuditEvent.entity_id == str(job_id),
            ).delete()
            db.query(CollectionJob).filter_by(id=job_id).delete()
            if draft_id is not None:
                db.query(ProductDraft).filter_by(id=draft_id).delete()
            if source_product_id is not None:
                db.query(SourceProduct).filter_by(id=source_product_id).delete()
            db.commit()
        engine.dispose()


@pytest.mark.skipif(not POSTGRES_URL, reason="TEST_POSTGRES_URL is not configured")
def test_postgres_serializes_mercado_libre_token_refresh():
    engine = create_engine(POSTGRES_URL, pool_pre_ping=True)
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    marker = uuid4().hex
    seller_id = f"refresh-{marker}"
    token_reference = f"meli:{seller_id}"
    with testing_session() as db:
        store = Store(
            site_id="MLM",
            seller_id=seller_id,
            display_name="Concurrent refresh test",
            oauth_status="connected",
            token_reference=token_reference,
        )
        db.add(store)
        db.flush()
        store_id = store.id
        db.add(
            TokenCredential(
                store_id=store_id,
                token_reference=token_reference,
                encrypted_access_token=encrypt_token_value("old-access", "test-secret"),
                encrypted_refresh_token=encrypt_token_value("old-refresh", "test-secret"),
                expires_at=datetime.now(UTC) + timedelta(seconds=10),
            )
        )
        db.commit()

    calls = 0
    calls_lock = Lock()

    class OAuthClient:
        async def refresh_token(self, refresh_token: str) -> MercadoLibreToken:
            nonlocal calls
            assert refresh_token == "old-refresh"
            with calls_lock:
                calls += 1
            await asyncio.sleep(0.2)
            return MercadoLibreToken(
                access_token="new-access",
                refresh_token="new-refresh",
                expires_in=21600,
                user_id=seller_id,
            )

    def resolve_token():
        with testing_session() as db:
            store = db.get(Store, store_id)
            token = asyncio.run(
                resolve_fresh_store_access_token(
                    db=db,
                    store=store,
                    encryption_key="test-secret",
                    oauth_client=OAuthClient(),
                )
            )
            return token, db.in_transaction()

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: resolve_token(), range(2)))
        assert [result[0] for result in results] == ["new-access", "new-access"]
        assert not any(result[1] for result in results)
        assert calls == 1
        with testing_session() as db:
            credential = db.query(TokenCredential).filter_by(store_id=store_id).one()
            assert (
                decrypt_token_value(credential.encrypted_refresh_token, "test-secret")
                == "new-refresh"
            )
    finally:
        with testing_session() as db:
            db.query(TokenCredential).filter_by(store_id=store_id).delete()
            db.query(Store).filter_by(id=store_id).delete()
            db.commit()
        engine.dispose()


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
