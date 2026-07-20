import pytest
from datetime import UTC, datetime, timedelta
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.draft_listing_config import DraftListingConfig
from app.models.draft_pricing_config import DraftPricingConfig
from app.models.product_draft import ProductDraft
from app.models.meli_metadata_cache import MeliMetadataCache
from app.models.product_draft_approval import ProductDraftApproval
from app.models.publish_job import PublishJob, PublishJobStatus
from app.models.registry import import_all_models
from app.models.review_result import ReviewDecision, ReviewResult
from app.models.store import Store
from app.models.token_credential import TokenCredential
from app.schemas.publishing import PublishExecutionResult
from app.services.meli.token_vault import encrypt_token_value
from app.workers.publish_worker import run_pending_publish_jobs
from app.workers import publish_worker
from pricing_test_support import add_current_pricing


def make_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    import_all_models()
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    with testing_session() as db:
        db.add(
            MeliMetadataCache(
                cache_key="category_attributes:MLM123",
                payload_json={"attributes": [{"id": "BRAND", "tags": {}}], "verified": True},
            )
        )
        store = Store(
            site_id="MLM",
            seller_id="seller-1",
            display_name="Demo Store",
            oauth_status="connected",
            token_reference="meli:seller-1",
        )
        db.add(store)
        db.flush()
        db.add(
            TokenCredential(
                store_id=store.id,
                token_reference="meli:seller-1",
                encrypted_access_token=encrypt_token_value("access-token", "test-secret"),
                encrypted_refresh_token=encrypt_token_value("refresh-token", "test-secret"),
            )
        )
        draft = ProductDraft(
            title="Worker Bottle",
            description="Leak proof.",
            brand="Demo",
            target_site_id="MLM",
            target_category_id="MLM123",
            price=9.99,
            currency="MXN",
            stock=2,
            image_urls_json=["https://example.com/a.jpg"],
        )
        db.add(draft)
        db.flush()
        add_current_pricing(db, draft)
        db.add(
            DraftListingConfig(
                product_draft_id=1,
                store_id=store.id,
                site_id="MLM",
                category_id="MLM123",
                listing_type_id="gold_special",
                fulfillment="classic",
                shipping_mode="me2",
                shipping_logistic_type="drop_off",
                attributes_json=[{"id": "BRAND", "value_name": "Demo"}],
            )
        )
        db.add(
            ProductDraftApproval(
                product_draft_id=1,
                status="approved",
                approved_by="operator",
                note="approved",
                review_result_id=1,
            )
        )
        db.add(
            ReviewResult(
                id=1,
                product_draft_id=1,
                provider="claude+nvidia_behavioral_audit",
                risk_level="low",
                decision=ReviewDecision.PASS,
                reasons_json={"reason_codes": [], "reasons": []},
                suggested_changes_json={},
                draft_version=1,
            )
        )
        db.commit()
    return testing_session


def job_summary(title: str = "Worker Bottle"):
    return {
        "title": title,
        "site_id": "MLM",
        "category_id": "MLM123",
        "listing_type_id": "gold_special",
        "review_provider": "claude",
        "review_result_id": 1,
        "review_decision": "pass",
        "review_risk_level": "low",
        "review_reason_codes": [],
        "review_reasons": [],
        "review_suggested_changes": {},
    }


@pytest.mark.asyncio
async def test_worker_publishes_pending_publish_jobs_up_to_limit():
    testing_session = make_session()
    with testing_session() as db:
        db.add(
            PublishJob(
                product_draft_id=1,
                store_id=1,
                requested_by="operator",
                status=PublishJobStatus.PENDING,
                request_summary_json=job_summary(),
            )
        )
        db.add(
            PublishJob(
                product_draft_id=1,
                store_id=1,
                requested_by="operator",
                status=PublishJobStatus.PENDING,
                request_summary_json=job_summary("Second Bottle"),
            )
        )
        db.commit()

    async def fake_publisher(**kwargs):
        assert kwargs["client"].access_token == "access-token"
        assert kwargs["seller_id"] == "seller-1"
        assert kwargs["listing_choice"].listing_type_id == "gold_special"
        assert kwargs["review"].provider == "claude+nvidia_behavioral_audit"
        return PublishExecutionResult(
            status="published",
            item_id="MLM-WORKER-1",
            permalink="https://example.com/MLM-WORKER-1",
        )

    with testing_session() as db:
        summary = await run_pending_publish_jobs(
            db,
            limit=1,
            publisher=fake_publisher,
            allow_live_publish=True,
            token_encryption_key="test-secret",
        )

    assert summary == {"processed": 1, "published": 1, "blocked": 0, "failed": 0, "recovered": 0}
    with testing_session() as db:
        jobs = db.query(PublishJob).order_by(PublishJob.id).all()
        assert [job.status for job in jobs] == [
            PublishJobStatus.PUBLISHED,
            PublishJobStatus.PENDING,
        ]
        assert jobs[0].meli_item_id == "MLM-WORKER-1"


@pytest.mark.asyncio
async def test_worker_skips_non_pending_publish_jobs():
    testing_session = make_session()
    with testing_session() as db:
        db.add(
            PublishJob(
                product_draft_id=1,
                store_id=1,
                requested_by="operator",
                status=PublishJobStatus.PUBLISHED,
                request_summary_json=job_summary(),
            )
        )
        db.commit()

    async def fake_publisher(**kwargs):
        raise AssertionError("publisher should not run")

    with testing_session() as db:
        summary = await run_pending_publish_jobs(
            db,
            limit=10,
            publisher=fake_publisher,
            allow_live_publish=True,
            token_encryption_key="test-secret",
        )

    assert summary == {"processed": 0, "published": 0, "blocked": 0, "failed": 0, "recovered": 0}


@pytest.mark.asyncio
async def test_worker_skips_job_claimed_by_another_worker(monkeypatch):
    testing_session = make_session()
    with testing_session() as db:
        db.add(
            PublishJob(
                product_draft_id=1,
                store_id=1,
                requested_by="operator",
                status=PublishJobStatus.PENDING,
                request_summary_json=job_summary(),
            )
        )
        db.commit()

    async def lost_claim(**kwargs):
        raise HTTPException(status_code=409, detail="claimed")

    monkeypatch.setattr(publish_worker, "run_pending_publish_job", lost_claim)
    with testing_session() as db:
        summary = await run_pending_publish_jobs(db)

    assert summary["processed"] == 0
    assert summary["failed"] == 0


@pytest.mark.asyncio
async def test_worker_rechecks_saved_listing_type_catalog_before_publisher():
    testing_session = make_session()
    with testing_session() as db:
        config = db.query(DraftListingConfig).one()
        config.listing_type_id = "gold_full"
        summary = job_summary()
        summary["valid_listing_type_ids"] = ["gold_special"]
        db.add(
            PublishJob(
                product_draft_id=1,
                store_id=1,
                requested_by="operator",
                status=PublishJobStatus.PENDING,
                request_summary_json=summary,
            )
        )
        db.commit()

    async def unexpected_publisher(**kwargs):
        raise AssertionError("invalid listing type must block before publisher")

    with testing_session() as db:
        summary = await run_pending_publish_jobs(
            db,
            limit=10,
            publisher=unexpected_publisher,
            allow_live_publish=True,
            token_encryption_key="test-secret",
        )

    assert summary == {"processed": 1, "published": 0, "blocked": 1, "failed": 0, "recovered": 0}
    with testing_session() as db:
        job = db.query(PublishJob).one()
        assert job.status == PublishJobStatus.BLOCKED
        assert "listing_type_not_supported" in job.response_summary_json["errors"]


@pytest.mark.asyncio
async def test_worker_blocks_job_without_current_saved_pricing():
    testing_session = make_session()
    with testing_session() as db:
        db.add(
            PublishJob(
                product_draft_id=1,
                store_id=1,
                requested_by="operator",
                status=PublishJobStatus.PENDING,
                request_summary_json=job_summary(),
            )
        )
        db.query(DraftPricingConfig).delete()
        db.commit()

    async def unexpected_publisher(**kwargs):
        raise AssertionError("missing pricing must block before the publisher")

    with testing_session() as db:
        summary = await run_pending_publish_jobs(
            db,
            publisher=unexpected_publisher,
            allow_live_publish=True,
            token_encryption_key="test-secret",
        )

    assert summary == {
        "processed": 1,
        "published": 0,
        "blocked": 1,
        "failed": 0,
        "recovered": 0,
    }
    with testing_session() as db:
        job = db.query(PublishJob).one()
        assert job.status == PublishJobStatus.BLOCKED
        assert job.response_summary_json["errors"] == ["saved_pricing_required"]


@pytest.mark.asyncio
async def test_worker_quarantines_stale_validating_publish_job():
    testing_session = make_session()
    with testing_session() as db:
        db.add(
            PublishJob(
                product_draft_id=1,
                store_id=1,
                requested_by="operator",
                status=PublishJobStatus.VALIDATING,
                started_at=datetime.now(UTC) - timedelta(hours=1),
                request_summary_json=job_summary(),
            )
        )
        db.commit()

    async def unexpected_publisher(**kwargs):
        raise AssertionError("unknown publish outcomes must not be retried automatically")

    with testing_session() as db:
        summary = await run_pending_publish_jobs(
            db,
            publisher=unexpected_publisher,
            allow_live_publish=True,
            token_encryption_key="test-secret",
        )

    assert summary["recovered"] == 1
    assert summary["processed"] == 0
    with testing_session() as db:
        job = db.query(PublishJob).one()
        assert job.status == PublishJobStatus.BLOCKED
        assert job.response_summary_json["errors"] == [
            "publish_outcome_unknown_manual_reconciliation_required"
        ]
