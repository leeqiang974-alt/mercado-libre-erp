from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import reviews
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.audit_event import AuditEvent
from app.models.draft_listing_config import DraftListingConfig
from app.models.meli_metadata_cache import MeliMetadataCache
from app.models.product_draft import ProductDraft
from app.models.review_job import ReviewJob, ReviewJobStatus
from app.models.review_result import ReviewDecision, ReviewResult
from app.models.registry import import_all_models
from app.models.store import Store
from app.schemas.reviews import BehavioralAuditResponse, ReviewResponse
from app.services.ai.provider_utils import AIProviderError
from app.services.integration_credentials import ResolvedIntegrationCredentials
from app.services import review_jobs as review_job_service
from app.services.review_jobs import enqueue_review_batch, recover_stale_review_jobs
from app.workers.review_worker import run_pending_review_jobs
from pricing_test_support import add_current_pricing


def make_client():
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
                payload_json={
                    "attributes": [
                        {
                            "id": "ITEM_CONDITION",
                            "value_type": "list",
                            "values": [{"id": "2230284", "name": "New"}],
                            "tags": {"hidden": True},
                        }
                    ],
                    "verified": True,
                },
            )
        )
        db.add(
            Store(
                id=1,
                site_id="MLM",
                seller_id="seller-1",
                display_name="Test Store",
                oauth_status="connected",
            )
        )
        for index in range(2):
            draft = ProductDraft(
                title=f"Bottle {index + 1}",
                description="Leak proof.",
                target_site_id="MLM",
                target_category_id="MLM123",
                source_price=300,
                source_currency="MXN",
                price=300,
                currency="MXN",
                stock=1,
                image_urls_json=["https://example.com/a.jpg"],
            )
            db.add(draft)
            db.flush()
            add_current_pricing(db, draft)
            db.add(
                DraftListingConfig(
                    product_draft_id=draft.id,
                    store_id=1,
                    site_id="MLM",
                    category_id="MLM123",
                    listing_type_id="gold_special",
                    fulfillment="not_full",
                    shipping_mode="me2",
                    shipping_logistic_type="drop_off",
                    available_quantity=1,
                    attributes_json=[
                        {
                            "id": "ITEM_CONDITION",
                            "value_id": "2230284",
                            "value_name": "New",
                        }
                    ],
                )
            )
        db.add(ProductDraft(title="Not configured", target_site_id="MLM"))
        db.commit()

    def override_get_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app), testing_session


def teardown_function():
    app.dependency_overrides.clear()


def configured_credentials(*args, **kwargs):
    return ResolvedIntegrationCredentials(
        meli_client_id="",
        meli_client_secret="",
        claude_api_key="claude-secret",
        nvidia_api_key="nvidia-secret",
    )


def test_batch_enqueue_requires_cost_acknowledgement_and_provider_credentials(monkeypatch):
    client, testing_session = make_client()

    no_ack = client.post(
        "/api/reviews/jobs/batch",
        json={"draft_ids": [1], "acknowledge_provider_costs": False},
    )
    missing_keys = client.post(
        "/api/reviews/jobs/batch",
        json={"draft_ids": [1], "acknowledge_provider_costs": True},
    )

    assert no_ack.status_code == 422
    assert missing_keys.status_code == 409
    assert missing_keys.json()["detail"]["code"] == "review_providers_not_configured"
    with testing_session() as db:
        assert db.query(ReviewJob).count() == 0

    monkeypatch.setattr(reviews, "resolve_integration_credentials", configured_credentials)
    queued = client.post(
        "/api/reviews/jobs/batch",
        json={"draft_ids": [1, 2, 3, 999], "acknowledge_provider_costs": True},
    )

    assert queued.status_code == 200
    assert queued.json()["queued_count"] == 2
    assert queued.json()["not_ready_count"] == 1
    assert queued.json()["not_found_count"] == 1
    assert [item["outcome"] for item in queued.json()["items"]] == [
        "queued",
        "queued",
        "not_ready",
        "not_found",
    ]
    repeated = client.post(
        "/api/reviews/jobs/batch",
        json={"draft_ids": [1], "acknowledge_provider_costs": True},
    )
    assert repeated.json()["existing_count"] == 1
    assert repeated.json()["items"][0]["job"]["id"] == queued.json()["items"][0]["job"]["id"]
    with testing_session() as db:
        assert db.query(ReviewJob).count() == 2
        assert db.query(AuditEvent).filter(AuditEvent.action == "review.batch.queued").count() == 2


def test_batch_enqueue_rolls_back_jobs_when_audit_write_fails(monkeypatch):
    _, testing_session = make_client()

    def fail_audit(*args, **kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(review_job_service, "create_audit_event", fail_audit)
    with testing_session() as db:
        with pytest.raises(RuntimeError, match="audit unavailable"):
            enqueue_review_batch(db, [1, 2])
        db.rollback()
        assert db.query(ReviewJob).count() == 0


def test_synchronous_audit_cannot_bypass_queued_execution_lease(monkeypatch):
    monkeypatch.setattr(reviews, "resolve_integration_credentials", configured_credentials)
    client, testing_session = make_client()
    with testing_session() as db:
        queued = enqueue_review_batch(db, [1])

    response = client.post(
        "/api/reviews/behavioral-audit?product_draft_id=1",
        json={"title": "ignored"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == {
        "code": "review_already_queued_or_running",
        "job_id": queued.items[0].job.id,
    }


def test_synchronous_provider_setup_failure_finishes_execution_lease(monkeypatch):
    client, testing_session = make_client()

    def fail_credentials(*args, **kwargs):
        raise RuntimeError("credential store unavailable")

    monkeypatch.setattr(reviews, "resolve_integration_credentials", fail_credentials)
    with pytest.raises(RuntimeError, match="credential store unavailable"):
        client.post(
            "/api/reviews/claude?product_draft_id=1",
            json={"title": "ignored"},
        )

    with testing_session() as db:
        job = db.query(ReviewJob).one()
        assert job.status == ReviewJobStatus.FAILED
        assert job.error_code == "review_execution_failed"
        assert job.active_key == "combined:1"
        assert db.query(AuditEvent).filter(
            AuditEvent.action == "review.job.finished"
        ).count() == 1


def test_synchronous_failed_job_retry_requires_new_cost_acknowledgement():
    client, testing_session = make_client()
    with testing_session() as db:
        queued = enqueue_review_batch(db, [1])
        job = db.get(ReviewJob, queued.items[0].job.id)
        job.status = ReviewJobStatus.FAILED
        job.error_code = "provider_unavailable"
        job.next_attempt_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()

    response = client.post(
        "/api/reviews/behavioral-audit?product_draft_id=1",
        json={"title": "ignored"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == {
        "code": "provider_cost_acknowledgement_required"
    }
    with testing_session() as db:
        job = db.query(ReviewJob).one()
        assert job.status == ReviewJobStatus.FAILED
        assert job.active_key == "combined:1"


async def successful_reviewer(db, product_draft_id: int) -> BehavioralAuditResponse:
    result = ReviewResult(
        product_draft_id=product_draft_id,
        provider="claude+nvidia_behavioral_audit",
        model="test-combined",
        prompt_version="meli-behavioral-audit-v4",
        risk_level="low",
        decision=ReviewDecision.PASS,
        reasons_json={"reason_codes": [], "reasons": []},
        draft_version=1,
    )
    db.add(result)
    db.commit()
    db.refresh(result)
    passed = ReviewResponse(
        provider="test",
        decision="pass",
        risk_level="low",
        reason_codes=[],
        reasons=[],
    )
    return BehavioralAuditResponse(
        nvidia=passed.model_copy(update={"provider": "nvidia"}),
        claude=passed.model_copy(update={"provider": "claude"}),
        aggregate=passed.model_copy(
            update={
                "provider": "claude+nvidia_behavioral_audit",
                "review_result_id": result.id,
            }
        ),
    )


@pytest.mark.asyncio
async def test_review_worker_completes_jobs_and_releases_active_key():
    _, testing_session = make_client()
    with testing_session() as db:
        queued = enqueue_review_batch(db, [1])
        job_id = queued.items[0].job.id

        summary = await run_pending_review_jobs(db, reviewer=successful_reviewer)

        assert summary["completed"] == 1
        job = db.get(ReviewJob, job_id)
        assert job.status == ReviewJobStatus.COMPLETED
        assert job.aggregate_review_result_id is not None
        assert job.active_key is None
        assert db.query(AuditEvent).filter(AuditEvent.action == "review.job.finished").count() == 1


@pytest.mark.asyncio
async def test_review_worker_pauses_remaining_jobs_after_rate_limit():
    _, testing_session = make_client()
    with testing_session() as db:
        queued = enqueue_review_batch(db, [1])

        async def rate_limited(db, product_draft_id):
            raise HTTPException(
                status_code=429,
                detail={
                    "provider": "nvidia",
                    "code": "rate_limited",
                    "retryable": True,
                    "retry_after_seconds": 45,
                },
            )

        before = datetime.now(UTC)
        summary = await run_pending_review_jobs(db, reviewer=rate_limited)

        assert summary["processed"] == 1
        assert summary["failed"] == 1
        retried = enqueue_review_batch(db, [1])
        newly_queued = enqueue_review_batch(db, [2])
        first = db.get(ReviewJob, queued.items[0].job.id)
        second = db.get(ReviewJob, newly_queued.items[0].job.id)
        assert retried.items[0].job.id == first.id
        assert first.status == ReviewJobStatus.PENDING
        assert first.error_code == ""
        assert first.next_attempt_at is not None
        assert second.status == ReviewJobStatus.PENDING
        assert second.next_attempt_at is not None
        assert second.next_attempt_at.replace(tzinfo=UTC) > before


@pytest.mark.asyncio
async def test_review_worker_blocks_without_provider_call_when_draft_changed_after_queue():
    _, testing_session = make_client()
    with testing_session() as db:
        queued = enqueue_review_batch(db, [1])
        draft = db.get(ProductDraft, 1)
        draft.content_version += 1
        db.commit()

        async def unexpected_reviewer(db, product_draft_id):
            raise AssertionError("changed queued content must not reach paid providers")

        summary = await run_pending_review_jobs(db, reviewer=unexpected_reviewer)

        assert summary["blocked"] == 1
        job = db.get(ReviewJob, queued.items[0].job.id)
        assert job.error_code == "draft_content_changed_after_review_queued"
        assert job.active_key is None


@pytest.mark.asyncio
async def test_review_worker_reuses_new_aggregate_persisted_after_queue():
    _, testing_session = make_client()
    with testing_session() as db:
        queued = enqueue_review_batch(db, [1])
        persisted = ReviewResult(
            product_draft_id=1,
            provider="claude+nvidia_behavioral_audit",
            model="persisted-before-job-finish",
            prompt_version="meli-behavioral-audit-v4",
            risk_level="low",
            decision=ReviewDecision.PASS,
            reasons_json={"reason_codes": [], "reasons": []},
            draft_version=1,
        )
        db.add(persisted)
        db.commit()
        db.refresh(persisted)

        async def unexpected_reviewer(db, product_draft_id):
            raise AssertionError("persisted aggregate must prevent duplicate paid calls")

        summary = await run_pending_review_jobs(db, reviewer=unexpected_reviewer)

        assert summary["completed"] == 1
        job = db.get(ReviewJob, queued.items[0].job.id)
        assert job.aggregate_review_result_id == persisted.id
        assert job.error_detail_json == {"reused_persisted_review": True}


def test_stale_review_job_recovers_persisted_aggregate_without_retry():
    _, testing_session = make_client()
    with testing_session() as db:
        queued = enqueue_review_batch(db, [1])
        job = db.get(ReviewJob, queued.items[0].job.id)
        job.status = ReviewJobStatus.RUNNING
        job.started_at = datetime.now(UTC) - timedelta(minutes=10)
        persisted = ReviewResult(
            product_draft_id=1,
            provider="claude+nvidia_behavioral_audit",
            model="persisted-before-crash",
            prompt_version="meli-behavioral-audit-v4",
            risk_level="low",
            decision=ReviewDecision.PASS,
            reasons_json={"reason_codes": [], "reasons": []},
            draft_version=1,
        )
        db.add(persisted)
        db.commit()
        db.refresh(persisted)

        assert recover_stale_review_jobs(db, stale_after_seconds=60) == 1
        db.refresh(job)
        assert job.status == ReviewJobStatus.COMPLETED
        assert job.aggregate_review_result_id == persisted.id
        assert job.active_key is None
        event = db.query(AuditEvent).filter(AuditEvent.action == "review.job.finished").one()
        assert event.after_json["recovered"] is True


def test_stale_review_job_without_aggregate_fails_without_automatic_retry():
    _, testing_session = make_client()
    with testing_session() as db:
        queued = enqueue_review_batch(db, [1])
        job = db.get(ReviewJob, queued.items[0].job.id)
        job.status = ReviewJobStatus.RUNNING
        job.started_at = datetime.now(UTC) - timedelta(minutes=10)
        db.commit()

        assert recover_stale_review_jobs(db, stale_after_seconds=60) == 1
        db.refresh(job)
        assert job.status == ReviewJobStatus.FAILED
        assert job.error_code == "review_worker_interrupted_manual_retry_required"
        assert job.active_key == "combined:1"
        assert job.next_attempt_at is None
        retried = enqueue_review_batch(db, [1])
        assert retried.items[0].job.id == job.id
        assert retried.items[0].job.status == "pending"


@pytest.mark.asyncio
async def test_manual_retry_reuses_paid_nvidia_result_when_claude_failed(monkeypatch):
    calls = {"nvidia": 0, "claude": 0}

    class CountingNvidiaClient:
        model = "nvidia-retry-test"
        prompt_version = "nvidia-retry-v1"

        def __init__(self, api_key: str, model: str = ""):
            pass

        async def pre_screen_draft(self, subject):
            calls["nvidia"] += 1
            return ReviewResponse(
                provider="nvidia",
                decision="pass",
                risk_level="low",
                reason_codes=[],
                reasons=[],
            )

    class RetryClaudeClient:
        model = "claude-retry-test"
        prompt_version = "claude-retry-v1"

        def __init__(self, api_key: str, model: str = ""):
            pass

        async def review_draft(self, subject):
            calls["claude"] += 1
            if calls["claude"] == 1:
                raise AIProviderError(
                    "claude",
                    "provider_unavailable",
                    http_status=503,
                    retryable=True,
                )
            return ReviewResponse(
                provider="claude",
                decision="pass",
                risk_level="low",
                reason_codes=[],
                reasons=[],
            )

    monkeypatch.setattr(reviews, "resolve_integration_credentials", configured_credentials)
    monkeypatch.setattr(reviews, "NvidiaReviewClient", CountingNvidiaClient)
    monkeypatch.setattr(reviews, "ClaudeReviewClient", RetryClaudeClient)
    _, testing_session = make_client()
    with testing_session() as db:
        first = enqueue_review_batch(db, [1])
        job_id = first.items[0].job.id

        failed = await run_pending_review_jobs(db)
        assert failed["failed"] == 1
        job = db.get(ReviewJob, job_id)
        assert job.active_key == "combined:1"

        retried = enqueue_review_batch(db, [1])
        assert retried.items[0].outcome == "queued"
        assert retried.items[0].job.id == job_id
        job.next_attempt_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()

        completed = await run_pending_review_jobs(db)
        assert completed["completed"] == 1
        assert calls == {"nvidia": 1, "claude": 2}
        rows = db.query(ReviewResult).filter(ReviewResult.review_job_id == job_id).all()
        assert sorted(row.provider for row in rows) == [
            "claude",
            "claude+nvidia_behavioral_audit",
            "nvidia",
        ]
