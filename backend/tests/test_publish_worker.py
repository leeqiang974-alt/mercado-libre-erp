import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.draft_listing_config import DraftListingConfig
from app.models.product_draft import ProductDraft
from app.models.product_draft_approval import ProductDraftApproval
from app.models.publish_job import PublishJob, PublishJobStatus
from app.models.registry import import_all_models
from app.models.store import Store
from app.models.token_credential import TokenCredential
from app.schemas.publishing import PublishExecutionResult
from app.services.meli.token_vault import encrypt_token_value
from app.workers.publish_worker import run_pending_publish_jobs


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
        db.add(
            ProductDraft(
                title="Worker Bottle",
                description="Leak proof.",
                brand="Demo",
                target_site_id="MLM",
                target_category_id="MLM123",
                price=9.99,
                currency="USD",
                stock=2,
                image_urls_json=["https://example.com/a.jpg"],
            )
        )
        db.flush()
        db.add(
            DraftListingConfig(
                product_draft_id=1,
                site_id="MLM",
                category_id="MLM123",
                listing_type_id="gold_special",
                fulfillment="classic",
                attributes_json=[{"id": "BRAND", "value_name": "Demo"}],
            )
        )
        db.add(
            ProductDraftApproval(
                product_draft_id=1,
                status="approved",
                approved_by="operator",
                note="approved",
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
        assert kwargs["listing_choice"].listing_type_id == "gold_special"
        assert kwargs["review"].provider == "claude"
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

    assert summary == {"processed": 1, "published": 1, "blocked": 0, "failed": 0}
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

    assert summary == {"processed": 0, "published": 0, "blocked": 0, "failed": 0}
