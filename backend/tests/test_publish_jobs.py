from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import publishing
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.audit_event import AuditEvent
from app.models.product_draft import ProductDraft
from app.models.meli_metadata_cache import MeliMetadataCache
from app.models.draft_listing_config import DraftListingConfig
from app.models.draft_pricing_config import DraftPricingConfig
from app.models.product_draft_approval import ProductDraftApproval
from app.models.publish_job import PublishJob, PublishJobStatus
from app.models.registry import import_all_models
from app.models.store import Store
from app.models.review_result import ReviewDecision, ReviewResult
from app.models.token_credential import TokenCredential
from app.schemas.drafts import ProductDraftCreate
from app.schemas.publishing import ListingChoice, PublishExecutionResult
from app.schemas.reviews import ReviewResponse
from app.services.meli.token_vault import encrypt_token_value
from app.services.publish_jobs import _publish_idempotency_key
from pricing_test_support import add_current_pricing


def make_client(with_token: bool = True):
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
        db.add(
            MeliMetadataCache(
                cache_key="category_attributes:MLA123",
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
        if with_token:
            db.add(
                TokenCredential(
                    store_id=store.id,
                    token_reference="meli:seller-1",
                    encrypted_access_token=encrypt_token_value("access-token", "test-secret"),
                    encrypted_refresh_token=encrypt_token_value("refresh-token", "test-secret"),
                )
            )
        draft = ProductDraft(
            title="Persisted Bottle",
            description="Leak proof.",
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
        db.add_all(
            [
                DraftListingConfig(
                    product_draft_id=draft.id,
                    store_id=store.id,
                    site_id="MLM",
                    category_id="MLM123",
                    listing_type_id="gold_special",
                    fulfillment="not_full",
                    shipping_mode="me2",
                    shipping_logistic_type="drop_off",
                    attributes_json=[],
                ),
                ProductDraftApproval(
                    product_draft_id=draft.id,
                    status="approved",
                    approved_by="operator",
                    draft_version=1,
                    review_result_id=1,
                ),
                ReviewResult(
                    id=1,
                    product_draft_id=draft.id,
                    provider="claude+nvidia_behavioral_audit",
                    prompt_version="meli-behavioral-audit-v4",
                    risk_level="low",
                    decision=ReviewDecision.PASS,
                    reasons_json={"reason_codes": [], "reasons": []},
                    suggested_changes_json={},
                    draft_version=1,
                ),
            ]
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


def payload():
    return {
        "store_id": 1,
        "draft": {
            "title": "Bottle",
            "description": "Leak proof.",
            "target_site_id": "MLM",
            "target_category_id": "MLM123",
            "price": 9.99,
            "currency": "MXN",
            "stock": 2,
            "image_urls": ["https://example.com/a.jpg"],
        },
        "review": {
            "provider": "claude+nvidia_behavioral_audit",
            "decision": "pass",
            "risk_level": "low",
            "reason_codes": [],
            "reasons": [],
            "suggested_changes": {},
            "review_result_id": 1,
        },
        "listing_choice": {
            "site_id": "MLM",
            "store_id": 1,
            "listing_type_id": "gold_special",
            "fulfillment": "not_full",
            "shipping_mode": "me2",
            "shipping_logistic_type": "drop_off",
        },
        "valid_listing_type_ids": ["gold_special"],
        "human_approved": True,
        "product_draft_id": 1,
    }


def test_publish_execute_persists_blocked_job_by_default(monkeypatch):
    monkeypatch.setattr(publishing.settings, "token_encryption_key", "test-secret")
    client, testing_session = make_client()

    response = client.post("/api/publishing/execute", json=payload())

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "blocked"
    assert body["job_id"] == 1
    with testing_session() as db:
        job = db.query(PublishJob).one()
        assert job.status == PublishJobStatus.BLOCKED
        assert job.product_draft_id == 1
        assert job.store_id == 1
        assert "live_publish_disabled" in job.response_summary_json["errors"]


def test_publish_execute_persists_published_job(monkeypatch):
    async def fake_execute_publish(**kwargs):
        with testing_session() as db:
            assert db.query(PublishJob).one().status == PublishJobStatus.VALIDATING
        return PublishExecutionResult(
            status="published",
            item_id="MLM123",
            permalink="https://example.com/MLM123",
        )

    monkeypatch.setattr(publishing.settings, "allow_live_publish", True)
    monkeypatch.setattr(publishing.settings, "token_encryption_key", "test-secret")
    monkeypatch.setattr(publishing, "execute_publish", fake_execute_publish)
    client, testing_session = make_client()

    response = client.post("/api/publishing/execute", json=payload())

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "published"
    assert body["job_id"] == 1
    with testing_session() as db:
        job = db.query(PublishJob).one()
        assert job.status == PublishJobStatus.PUBLISHED
        assert job.meli_item_id == "MLM123"
        assert job.permalink == "https://example.com/MLM123"
        assert job.request_summary_json["store_id"] == 1
        assert job.request_summary_json["shipping_mode"] == "me2"
        assert job.request_summary_json["shipping_logistic_type"] == "drop_off"


def test_shipping_selection_changes_publish_idempotency_key():
    draft = ProductDraftCreate(**payload()["draft"])
    review = ReviewResponse(**payload()["review"])
    first = ListingChoice(**payload()["listing_choice"])
    second = first.model_copy(update={"shipping_logistic_type": "self_service"})

    assert _publish_idempotency_key(1, 1, draft, review, first) != _publish_idempotency_key(
        1, 1, draft, review, second
    )


def test_publish_execute_quarantines_unexpected_adapter_exception(monkeypatch):
    async def failed_after_request(**kwargs):
        raise RuntimeError("response parsing failed")

    monkeypatch.setattr(publishing.settings, "allow_live_publish", True)
    monkeypatch.setattr(publishing.settings, "token_encryption_key", "test-secret")
    monkeypatch.setattr(publishing, "execute_publish", failed_after_request)
    client, testing_session = make_client()

    response = client.post("/api/publishing/execute", json=payload())

    assert response.status_code == 200
    assert response.json()["status"] == "blocked"
    assert response.json()["errors"] == ["publish_outcome_unknown_manual_reconciliation_required"]
    with testing_session() as db:
        job = db.query(PublishJob).one()
        assert job.status == PublishJobStatus.BLOCKED


def test_publish_execute_persists_blocked_job_when_store_token_is_missing(monkeypatch):
    monkeypatch.setattr(publishing.settings, "allow_live_publish", True)
    monkeypatch.setattr(publishing.settings, "token_encryption_key", "test-secret")
    client, testing_session = make_client(with_token=False)

    response = client.post("/api/publishing/execute", json=payload())

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "blocked"
    assert body["job_id"] == 1
    with testing_session() as db:
        job = db.query(PublishJob).one()
        audit = db.query(AuditEvent).filter(AuditEvent.action == "publish.executed").one()
        assert job.status == PublishJobStatus.BLOCKED
        assert job.response_summary_json["errors"] == ["store_access_token_required"]
        assert audit.entity_id == "1"
        assert audit.after_json["errors"] == ["store_access_token_required"]


def test_publish_execute_invalidates_review_when_store_site_no_longer_matches(monkeypatch):
    monkeypatch.setattr(publishing.settings, "allow_live_publish", True)
    monkeypatch.setattr(publishing.settings, "token_encryption_key", "test-secret")

    async def unexpected_publish(**kwargs):
        raise AssertionError("site mismatch must block before the publisher")

    monkeypatch.setattr(publishing, "execute_publish", unexpected_publish)
    client, testing_session = make_client()
    with testing_session() as db:
        config = db.query(DraftListingConfig).one()
        config.site_id = "MLA"
        config.category_id = "MLA123"
        draft = db.get(ProductDraft, 1)
        draft.target_site_id = "MLA"
        draft.currency = "ARS"
        pricing = db.query(DraftPricingConfig).one()
        pricing.target_currency = "ARS"
        db.commit()
    body = payload()
    body["draft"]["target_site_id"] = "MLA"
    body["listing_choice"]["site_id"] = "MLA"

    response = client.post("/api/publishing/execute", json=body)

    assert response.status_code == 422
    assert response.json()["detail"] == "latest_behavioral_review_required"
    with testing_session() as db:
        assert db.query(PublishJob).count() == 0


def test_publish_jobs_can_be_listed():
    client, testing_session = make_client()
    with testing_session() as db:
        db.add(
            PublishJob(
                product_draft_id=1,
                store_id=1,
                requested_by="operator",
                status=PublishJobStatus.BLOCKED,
                response_summary_json={"errors": ["live_publish_disabled"]},
            )
        )
        db.commit()

    response = client.get("/api/publishing/jobs")

    assert response.status_code == 200
    body = response.json()
    assert body[0]["id"] == 1
    assert body[0]["status"] == "blocked"
    assert body[0]["errors"] == ["live_publish_disabled"]
