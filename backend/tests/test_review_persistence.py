import asyncio

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import reviews
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.product_draft import ProductDraft
from app.models.draft_listing_config import DraftListingConfig
from app.models.meli_metadata_cache import MeliMetadataCache
from app.models.registry import import_all_models
from app.models.review_result import ReviewDecision, ReviewResult
from app.models.store import Store
from app.models.audit_event import AuditEvent
from app.schemas.reviews import ReviewResponse
from app.services.ai.provider_utils import AIProviderError
from app.services import reviews as review_service
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
        draft = ProductDraft(
                title="Bottle",
                description="Leak proof.",
                target_site_id="MLM",
                target_category_id="MLM123",
                price=9.99,
                currency="MXN",
                stock=1,
                image_urls_json=["https://example.com/a.jpg"],
            )
        db.add(draft)
        db.flush()
        add_current_pricing(db, draft)
        db.add(
            Store(
                id=1,
                site_id="MLM",
                seller_id="seller-1",
                display_name="Test Store",
                oauth_status="connected",
            )
        )
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
                    {"id": "ITEM_CONDITION", "value_id": "2230284", "value_name": "New"}
                ],
            )
        )
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


def draft_payload():
    return {
        "title": "Bottle",
        "description": "Leak proof.",
        "target_site_id": "MLM",
        "price": 9.99,
        "currency": "MXN",
        "stock": 1,
        "image_urls": ["https://example.com/a.jpg"],
    }


def test_local_review_can_persist_result_for_draft():
    client, testing_session = make_client()

    response = client.post("/api/reviews/local?product_draft_id=1", json=draft_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "local_policy"
    assert body["review_result_id"] == 1
    with testing_session() as db:
        row = db.query(ReviewResult).one()
        assert row.product_draft_id == 1
        assert row.provider == "local_policy"
        assert row.decision.value == "pass"


def test_review_history_can_be_listed_for_draft():
    client, _ = make_client()
    client.post("/api/reviews/local?product_draft_id=1", json=draft_payload())

    response = client.get("/api/reviews/drafts/1")

    assert response.status_code == 200
    body = response.json()
    assert body[0]["id"] == 1
    assert body[0]["provider"] == "local_policy"
    assert body[0]["model"] == "local-policy"
    assert body[0]["prompt_version"] == "local-policy-v1"
    assert body[0]["provider_status"] == "completed"
    assert body[0]["duration_ms"] >= 0
    assert body[0]["created_at"]
    assert body[0]["decision"] == "pass"


def test_latest_behavioral_review_excludes_stale_draft_versions():
    client, testing_session = make_client()
    with testing_session() as db:
        result = ReviewResult(
            product_draft_id=1,
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
        result_id = result.id

    current = client.get("/api/reviews/drafts/1/latest-behavioral")
    assert current.status_code == 200
    assert current.json()["id"] == result_id

    with testing_session() as db:
        draft = db.get(ProductDraft, 1)
        draft.content_version += 1
        db.commit()

    stale = client.get("/api/reviews/drafts/1/latest-behavioral")
    assert stale.status_code == 200
    assert stale.json() is None


def test_claude_review_can_persist_result_for_draft(monkeypatch):
    class FakeClaudeClient:
        model = "claude-test"
        prompt_version = "meli-safety-test-v1"

        def __init__(self, api_key: str, model: str = ""):
            pass

        async def review_draft(self, subject):
            assert subject.draft.source_price == 9.99
            assert subject.draft.source_currency == "MXN"
            assert subject.pricing.source_price == 9.99
            assert subject.pricing.target_currency == "MXN"
            assert subject.listing.site_id == "MLM"
            assert subject.listing.listing_type_id == "gold_special"
            assert subject.listing.fulfillment == "not_full"
            assert subject.listing.authorized_store_id == 1
            assert subject.listing.shipping_logistic_type == "drop_off"
            return ReviewResponse(
                provider="claude",
                decision="needs_human_review",
                risk_level="medium",
                reason_codes=["brand_risk"],
                reasons=["verify"],
                input_tokens=125,
                output_tokens=25,
                total_tokens=150,
                provider_request_id="req_claude_persisted",
            )

    monkeypatch.setattr(reviews, "ClaudeReviewClient", FakeClaudeClient)
    client, testing_session = make_client()

    response = client.post("/api/reviews/claude?product_draft_id=1", json=draft_payload())

    assert response.status_code == 200
    assert response.json()["review_result_id"] == 1
    with testing_session() as db:
        row = db.query(ReviewResult).one()
        assert row.provider == "claude"
        assert row.model == "claude-test"
        assert row.prompt_version == "meli-safety-test-v1"
        assert row.duration_ms >= 0
        assert row.provider_status == "completed"
        assert row.input_tokens == 125
        assert row.output_tokens == 25
        assert row.total_tokens == 150
        assert row.provider_request_id == "req_claude_persisted"
        assert row.decision.value == "needs_human_review"


def test_provider_review_requires_store_and_non_full_shipping_context(monkeypatch):
    class UnexpectedClaudeClient:
        def __init__(self, api_key: str, model: str = ""):
            pass

        async def review_draft(self, subject):
            raise AssertionError("incomplete listing context must block before provider call")

    monkeypatch.setattr(reviews, "ClaudeReviewClient", UnexpectedClaudeClient)
    client, testing_session = make_client()
    with testing_session() as db:
        listing = db.query(DraftListingConfig).one()
        listing.store_id = None
        listing.shipping_mode = ""
        listing.shipping_logistic_type = ""
        db.commit()

    response = client.post("/api/reviews/claude?product_draft_id=1", json=draft_payload())

    assert response.status_code == 409
    assert response.json()["detail"] == {
        "code": "review_listing_context_incomplete",
        "errors": [
            "authorized_store_selection_required",
            "non_full_shipping_mode_invalid",
            "non_full_shipping_logistic_type_invalid",
        ],
    }
    with testing_session() as db:
        assert db.query(ReviewResult).count() == 0


def test_provider_result_is_not_persisted_when_store_disconnects_during_review(monkeypatch):
    class DisconnectingClaudeClient:
        def __init__(self, api_key: str, model: str = ""):
            pass

        async def review_draft(self, subject):
            with testing_session() as other_db:
                store = other_db.get(Store, 1)
                store.oauth_status = "disconnected"
                other_db.commit()
            return ReviewResponse(
                provider="claude",
                decision="pass",
                risk_level="low",
                reason_codes=[],
                reasons=[],
            )

    monkeypatch.setattr(reviews, "ClaudeReviewClient", DisconnectingClaudeClient)
    client, testing_session = make_client()

    response = client.post("/api/reviews/claude?product_draft_id=1", json=draft_payload())

    assert response.status_code == 409
    assert response.json()["detail"] == {
        "code": "review_listing_context_not_current",
        "errors": ["store_not_connected"],
    }
    with testing_session() as db:
        assert db.query(ReviewResult).count() == 0


def test_provider_review_rejects_full_logistic_type_before_provider_call(monkeypatch):
    class UnexpectedNvidiaClient:
        def __init__(self, api_key: str, model: str = ""):
            pass

        async def pre_screen_draft(self, subject):
            raise AssertionError("FULL logistics must block before provider call")

    monkeypatch.setattr(reviews, "NvidiaReviewClient", UnexpectedNvidiaClient)
    client, testing_session = make_client()
    with testing_session() as db:
        listing = db.query(DraftListingConfig).one()
        listing.shipping_logistic_type = "fulfillment"
        db.commit()

    response = client.post("/api/reviews/nvidia?product_draft_id=1", json=draft_payload())

    assert response.status_code == 409
    assert response.json()["detail"] == {
        "code": "review_listing_context_incomplete",
        "errors": ["non_full_shipping_logistic_type_invalid"],
    }


def test_provider_review_rejects_non_classic_premium_listing_before_provider_call(monkeypatch):
    class UnexpectedNvidiaClient:
        def __init__(self, api_key: str, model: str = ""):
            pass

        async def pre_screen_draft(self, subject):
            raise AssertionError("unsupported listing type must block before provider call")

    monkeypatch.setattr(reviews, "NvidiaReviewClient", UnexpectedNvidiaClient)
    client, testing_session = make_client()
    with testing_session() as db:
        listing = db.query(DraftListingConfig).one()
        listing.listing_type_id = "gold_full"
        db.commit()

    response = client.post("/api/reviews/nvidia?product_draft_id=1", json=draft_payload())

    assert response.status_code == 409
    assert response.json()["detail"] == {
        "code": "review_listing_context_incomplete",
        "errors": ["listing_type_not_supported"],
    }


def test_nvidia_review_can_persist_result_for_draft(monkeypatch):
    class FakeNvidiaClient:
        def __init__(self, api_key: str, model: str = ""):
            pass

        async def pre_screen_draft(self, draft):
            return ReviewResponse(
                provider="nvidia",
                decision="block",
                risk_level="high",
                reason_codes=["restricted_item"],
                reasons=["blocked"],
            )

    monkeypatch.setattr(reviews, "NvidiaReviewClient", FakeNvidiaClient)
    client, testing_session = make_client()

    response = client.post("/api/reviews/nvidia?product_draft_id=1", json=draft_payload())

    assert response.status_code == 200
    assert response.json()["review_result_id"] == 1
    with testing_session() as db:
        row = db.query(ReviewResult).one()
        assert row.provider == "nvidia"
        assert row.decision.value == "block"


def test_behavioral_audit_persists_both_provider_results_and_orchestration_audit(monkeypatch):
    class FakeClaudeClient:
        model = "claude-test"
        prompt_version = "claude-prompt-v2"

        def __init__(self, api_key: str, model: str = ""):
            pass

        async def review_draft(self, draft):
            return ReviewResponse(
                provider="claude",
                decision="pass",
                risk_level="low",
                reason_codes=[],
                reasons=[],
            )

    class FakeNvidiaClient:
        model = "nvidia-test"
        prompt_version = "nvidia-prompt-v3"

        def __init__(self, api_key: str, model: str = ""):
            pass

        async def pre_screen_draft(self, draft):
            return ReviewResponse(
                provider="nvidia",
                decision="needs_human_review",
                risk_level="medium",
                reason_codes=["verify"],
                reasons=["verify"],
            )

    monkeypatch.setattr(reviews, "ClaudeReviewClient", FakeClaudeClient)
    monkeypatch.setattr(reviews, "NvidiaReviewClient", FakeNvidiaClient)
    client, testing_session = make_client()

    response = client.post(
        "/api/reviews/behavioral-audit?product_draft_id=1",
        json=draft_payload(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["aggregate"]["decision"] == "needs_human_review"
    assert {body["nvidia"]["review_result_id"], body["claude"]["review_result_id"]} == {1, 2}
    with testing_session() as db:
        rows = db.query(ReviewResult).order_by(ReviewResult.id).all()
        assert [(row.provider, row.model) for row in rows] == [
            ("nvidia", "nvidia-test"),
            ("claude", "claude-test"),
            ("claude+nvidia_behavioral_audit", "nvidia-test+claude-test"),
        ]
        assert [row.prompt_version for row in rows] == [
            "nvidia-prompt-v3",
            "claude-prompt-v2",
            "meli-behavioral-audit-v4",
        ]
        assert all(row.duration_ms >= 0 for row in rows)
        assert all(row.provider_status == "completed" for row in rows)
        assert body["aggregate"]["review_result_id"] == 3
        audit = db.query(AuditEvent).filter(AuditEvent.action == "review.behavioral_audit.completed").one()
        assert audit.actor_id == "claude+nvidia"
        assert audit.after_json["prompt_versions"] == [
            "nvidia-prompt-v3",
            "claude-prompt-v2",
        ]


def test_failed_provider_attempt_is_audited_without_success_result(monkeypatch):
    class FailedClaudeClient:
        model = "claude-failed-model"
        prompt_version = "meli-safety-failed-v1"

        def __init__(self, api_key: str, model: str = ""):
            pass

        async def review_draft(self, draft):
            raise AIProviderError("claude", "request_failed")

    monkeypatch.setattr(reviews, "ClaudeReviewClient", FailedClaudeClient)
    client, testing_session = make_client()

    response = client.post(
        "/api/reviews/claude?product_draft_id=1",
        json=draft_payload(),
    )

    assert response.status_code == 503
    with testing_session() as db:
        assert db.query(ReviewResult).count() == 0
        event = db.query(AuditEvent).filter(AuditEvent.action == "review.failed").one()
        assert event.actor_id == "claude"
        assert event.after_json == {
            "provider_status": "failed",
            "error_code": "request_failed",
            "model": "claude-failed-model",
            "prompt_version": "meli-safety-failed-v1",
            "duration_ms": event.after_json["duration_ms"],
            "http_status": None,
            "retryable": False,
            "retry_after_seconds": None,
            "provider_request_id": "",
        }
        assert event.after_json["duration_ms"] >= 0


def test_rate_limit_attempt_persists_operator_retry_evidence(monkeypatch):
    class RateLimitedClaudeClient:
        model = "claude-rate-limited"
        prompt_version = "meli-safety-v1"

        def __init__(self, api_key: str, model: str = ""):
            pass

        async def review_draft(self, draft):
            raise AIProviderError(
                "claude",
                "rate_limited",
                http_status=429,
                retryable=True,
                retry_after_seconds=31,
                request_id="req_persisted_429",
            )

    monkeypatch.setattr(reviews, "ClaudeReviewClient", RateLimitedClaudeClient)
    client, testing_session = make_client()

    response = client.post(
        "/api/reviews/claude?product_draft_id=1",
        json=draft_payload(),
    )

    assert response.status_code == 429
    with testing_session() as db:
        assert db.query(ReviewResult).count() == 0
        event = db.query(AuditEvent).filter(AuditEvent.action == "review.failed").one()
        assert event.after_json["error_code"] == "rate_limited"
        assert event.after_json["http_status"] == 429
        assert event.after_json["retryable"] is True
        assert event.after_json["retry_after_seconds"] == 31
        assert event.after_json["provider_request_id"] == "req_persisted_429"


def test_behavioral_audit_keeps_nvidia_evidence_when_claude_fails(monkeypatch):
    class SuccessfulNvidiaClient:
        model = "nvidia-paid-request"
        prompt_version = "meli-safety-v1"

        def __init__(self, api_key: str, model: str = ""):
            pass

        async def pre_screen_draft(self, draft):
            return ReviewResponse(
                provider="nvidia",
                decision="pass",
                risk_level="low",
                reason_codes=[],
                reasons=[],
                input_tokens=70,
                output_tokens=10,
                total_tokens=80,
                provider_request_id="req_nvidia_paid",
            )

    class FailedClaudeClient:
        model = "claude-failed"
        prompt_version = "meli-safety-v1"

        def __init__(self, api_key: str, model: str = ""):
            pass

        async def review_draft(self, draft):
            raise AIProviderError(
                "claude",
                "provider_unavailable",
                http_status=529,
                retryable=True,
                request_id="req_claude_failed",
            )

    monkeypatch.setattr(reviews, "NvidiaReviewClient", SuccessfulNvidiaClient)
    monkeypatch.setattr(reviews, "ClaudeReviewClient", FailedClaudeClient)
    client, testing_session = make_client()

    response = client.post(
        "/api/reviews/behavioral-audit?product_draft_id=1",
        json=draft_payload(),
    )

    assert response.status_code == 503
    with testing_session() as db:
        result = db.query(ReviewResult).one()
        assert result.provider == "nvidia"
        assert result.total_tokens == 80
        assert result.provider_request_id == "req_nvidia_paid"
        actions = [event.action for event in db.query(AuditEvent).order_by(AuditEvent.id)]
        assert actions == ["review.completed", "review.failed", "review.job.finished"]


def test_behavioral_results_roll_back_when_batch_audit_fails(monkeypatch):
    class FakeClaudeClient:
        model = "claude-test"
        prompt_version = "claude-prompt-v1"

        def __init__(self, api_key: str, model: str = ""):
            pass

        async def review_draft(self, draft):
            return ReviewResponse(
                provider="claude",
                decision="pass",
                risk_level="low",
                reason_codes=[],
                reasons=[],
            )

    class FakeNvidiaClient:
        model = "nvidia-test"
        prompt_version = "nvidia-prompt-v1"

        def __init__(self, api_key: str, model: str = ""):
            pass

        async def pre_screen_draft(self, draft):
            return ReviewResponse(
                provider="nvidia",
                decision="pass",
                risk_level="low",
                reason_codes=[],
                reasons=[],
            )

    original_create_audit_event = review_service.create_audit_event

    def fail_batch_audit(*args, **kwargs):
        if kwargs.get("action") == "review.behavioral_audit.completed":
            raise RuntimeError("batch audit unavailable")
        return original_create_audit_event(*args, **kwargs)

    monkeypatch.setattr(reviews, "ClaudeReviewClient", FakeClaudeClient)
    monkeypatch.setattr(reviews, "NvidiaReviewClient", FakeNvidiaClient)
    monkeypatch.setattr(review_service, "create_audit_event", fail_batch_audit)
    client, testing_session = make_client()

    with pytest.raises(RuntimeError, match="batch audit unavailable"):
        client.post(
            "/api/reviews/behavioral-audit?product_draft_id=1",
            json=draft_payload(),
        )

    with testing_session() as db:
        assert [row.provider for row in db.query(ReviewResult).order_by(ReviewResult.id)] == [
            "nvidia",
            "claude",
        ]
        assert [event.action for event in db.query(AuditEvent).order_by(AuditEvent.id)] == [
            "review.completed",
            "review.completed",
            "review.job.finished",
        ]


def test_claude_review_rejects_result_when_draft_changes_while_provider_waits(monkeypatch):
    client, testing_session = make_client()

    class VersionChangingClaudeClient:
        def __init__(self, api_key: str, model: str = ""):
            pass

        async def review_draft(self, draft):
            await asyncio.sleep(0)
            with testing_session() as other_db:
                persisted = other_db.get(ProductDraft, 1)
                persisted.content_version += 1
                other_db.commit()
            return ReviewResponse(
                provider="claude",
                decision="pass",
                risk_level="low",
                reason_codes=[],
                reasons=[],
                input_tokens=51,
                output_tokens=9,
                total_tokens=60,
                provider_request_id="req_stale_claude",
            )

    monkeypatch.setattr(reviews, "ClaudeReviewClient", VersionChangingClaudeClient)

    response = client.post("/api/reviews/claude?product_draft_id=1", json=draft_payload())

    assert response.status_code == 409
    assert response.json()["detail"] == "draft_content_version_changed_during_review"
    with testing_session() as db:
        result = db.query(ReviewResult).one()
        assert result.provider == "claude"
        assert result.provider_status == "completed_stale"
        assert result.draft_version == 1
        assert result.total_tokens == 60
        assert result.provider_request_id == "req_stale_claude"
        event = db.query(AuditEvent).filter(AuditEvent.action == "review.completed_stale").one()
        assert event.action == "review.completed_stale"
        assert event.after_json["reviewed_draft_version"] == 1
        assert event.after_json["current_draft_version"] == 2


def test_behavioral_audit_rejects_all_results_when_draft_changes_while_provider_waits(
    monkeypatch,
):
    client, testing_session = make_client()

    class FakeNvidiaClient:
        def __init__(self, api_key: str, model: str = ""):
            pass

        async def pre_screen_draft(self, draft):
            return ReviewResponse(
                provider="nvidia",
                decision="pass",
                risk_level="low",
                reason_codes=[],
                reasons=[],
            )

    class VersionChangingClaudeClient:
        def __init__(self, api_key: str, model: str = ""):
            pass

        async def review_draft(self, draft):
            await asyncio.sleep(0)
            with testing_session() as other_db:
                persisted = other_db.get(ProductDraft, 1)
                persisted.content_version += 1
                other_db.commit()
            return ReviewResponse(
                provider="claude",
                decision="pass",
                risk_level="low",
                reason_codes=[],
                reasons=[],
                input_tokens=41,
                output_tokens=7,
                total_tokens=48,
                provider_request_id="req_stale_behavioral_claude",
            )

    monkeypatch.setattr(reviews, "NvidiaReviewClient", FakeNvidiaClient)
    monkeypatch.setattr(reviews, "ClaudeReviewClient", VersionChangingClaudeClient)

    response = client.post(
        "/api/reviews/behavioral-audit?product_draft_id=1",
        json=draft_payload(),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "draft_content_version_changed_during_review"
    with testing_session() as db:
        rows = db.query(ReviewResult).order_by(ReviewResult.id).all()
        assert [(row.provider, row.provider_status) for row in rows] == [
            ("nvidia", "completed"),
            ("claude", "completed_stale"),
        ]
        assert [event.action for event in db.query(AuditEvent).order_by(AuditEvent.id)] == [
            "review.completed",
            "review.completed_stale",
            "review.job.finished",
        ]
