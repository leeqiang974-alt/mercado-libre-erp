from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import publishing
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.audit_event import AuditEvent
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
            title="Persisted Bottle",
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


def job_summary():
    return {
        "title": "Persisted Bottle",
        "site_id": "MLM",
        "category_id": "MLM123",
        "listing_type_id": "gold_special",
        "review_provider": "claude+nvidia_behavioral_audit",
        "review_result_id": 1,
        "review_decision": "pass",
        "review_risk_level": "low",
        "review_reason_codes": [],
        "review_reasons": [],
        "review_suggested_changes": {},
    }


def test_blocked_publish_job_can_be_retried_from_saved_draft_config(monkeypatch):
    async def fake_execute_publish(**kwargs):
        assert kwargs["client"].access_token == "access-token"
        assert kwargs["listing_choice"].listing_type_id == "gold_special"
        assert kwargs["listing_choice"].fulfillment == "classic"
        assert kwargs["review"].provider == "claude+nvidia_behavioral_audit"
        assert kwargs["review"].decision == "pass"
        assert kwargs["human_approved"] is True
        return PublishExecutionResult(
            status="published",
            item_id="MLM999",
            permalink="https://example.com/MLM999",
        )

    monkeypatch.setattr(publishing.settings, "allow_live_publish", True)
    monkeypatch.setattr(publishing.settings, "token_encryption_key", "test-secret")
    monkeypatch.setattr(publishing, "execute_publish", fake_execute_publish)
    client, testing_session = make_client()
    with testing_session() as db:
        db.add(
            PublishJob(
                product_draft_id=1,
                store_id=1,
                requested_by="operator",
                status=PublishJobStatus.BLOCKED,
                request_summary_json=job_summary(),
                response_summary_json={"errors": ["live_publish_disabled"]},
            )
        )
        db.commit()

    response = client.post("/api/publishing/jobs/1/retry")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "published"
    assert body["job_id"] == 1
    with testing_session() as db:
        retry = db.get(PublishJob, 1)
        retry_audit = (
            db.query(AuditEvent).filter(AuditEvent.action == "publish.retry_requested").one()
        )
        assert retry.status == PublishJobStatus.PUBLISHED
        assert retry.meli_item_id == "MLM999"
        assert retry.request_summary_json["review_provider"] == "claude+nvidia_behavioral_audit"
        assert retry_audit.entity_id == "1"
        assert retry_audit.after_json["retry_store_id"] == 1
        assert retry_audit.after_json["shipping_mode"] == "me2"
        assert retry_audit.after_json["shipping_logistic_type"] == "drop_off"


def test_retry_requires_current_saved_pricing(monkeypatch):
    async def unexpected_publish(**kwargs):
        raise AssertionError("missing pricing must block before the publisher")

    monkeypatch.setattr(publishing, "execute_publish", unexpected_publish)
    client, testing_session = make_client()
    with testing_session() as db:
        db.add(
            PublishJob(
                product_draft_id=1,
                store_id=1,
                requested_by="operator",
                status=PublishJobStatus.BLOCKED,
                request_summary_json=job_summary(),
                response_summary_json={"errors": ["live_publish_disabled"]},
            )
        )
        db.query(DraftPricingConfig).delete()
        db.commit()

    response = client.post("/api/publishing/jobs/1/retry")

    assert response.status_code == 409
    assert "saved_pricing_required" in response.text
    with testing_session() as db:
        assert db.get(PublishJob, 1).status == PublishJobStatus.BLOCKED


def test_published_publish_job_cannot_be_retried():
    client, testing_session = make_client()
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

    response = client.post("/api/publishing/jobs/1/retry")

    assert response.status_code == 400
    assert response.json()["detail"] == "Only blocked or failed publish jobs can be retried."


def test_unknown_publish_outcome_cannot_be_retried():
    client, testing_session = make_client()
    with testing_session() as db:
        db.add(
            PublishJob(
                product_draft_id=1,
                store_id=1,
                requested_by="operator",
                status=PublishJobStatus.BLOCKED,
                request_summary_json=job_summary(),
                response_summary_json={
                    "errors": ["publish_outcome_unknown_manual_reconciliation_required"]
                },
            )
        )
        db.commit()

    response = client.post("/api/publishing/jobs/1/retry")

    assert response.status_code == 409
    assert "reconcile the store" in response.json()["detail"]


def test_description_failure_with_created_item_cannot_be_retried(monkeypatch):
    async def unexpected_publish(**kwargs):
        raise AssertionError("an existing item id must never create a replacement")

    monkeypatch.setattr(publishing, "execute_publish", unexpected_publish)
    client, testing_session = make_client()
    with testing_session() as db:
        db.add(
            PublishJob(
                product_draft_id=1,
                store_id=1,
                requested_by="operator",
                status=PublishJobStatus.FAILED,
                meli_item_id="MLM-DESCRIPTION-1",
                request_summary_json=job_summary(),
                response_summary_json={
                    "errors": ["meli_description_failed:422"]
                },
            )
        )
        db.commit()

    response = client.post("/api/publishing/jobs/1/retry")

    assert response.status_code == 409
    assert "already created an item" in response.json()["detail"]


def test_retry_preflight_failure_keeps_terminal_job_state():
    client, testing_session = make_client()
    with testing_session() as db:
        db.add(
            PublishJob(
                product_draft_id=1,
                store_id=1,
                requested_by="operator",
                status=PublishJobStatus.BLOCKED,
                request_summary_json=job_summary(),
                response_summary_json={"errors": ["live_publish_disabled"]},
            )
        )
        db.add(
            ReviewResult(
                product_draft_id=1,
                provider="claude+nvidia_behavioral_audit",
                risk_level="high",
                decision=ReviewDecision.BLOCK,
                reasons_json={"reason_codes": ["new_block"], "reasons": ["blocked"]},
                suggested_changes_json={},
                draft_version=1,
            )
        )
        db.commit()

    response = client.post("/api/publishing/jobs/1/retry")

    assert response.status_code == 422
    assert response.json()["detail"] == "latest_behavioral_review_required"
    with testing_session() as db:
        assert db.get(PublishJob, 1).status == PublishJobStatus.BLOCKED
