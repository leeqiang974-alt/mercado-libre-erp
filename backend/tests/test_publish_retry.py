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
from app.models.product_draft import ProductDraft
from app.models.product_draft_approval import ProductDraftApproval
from app.models.publish_job import PublishJob, PublishJobStatus
from app.models.registry import import_all_models
from app.models.store import Store
from app.models.token_credential import TokenCredential
from app.schemas.publishing import PublishExecutionResult
from app.services.meli.token_vault import encrypt_token_value


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
                title="Persisted Bottle",
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
        "review_provider": "claude",
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
        assert kwargs["review"].provider == "claude"
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
    assert body["job_id"] == 2
    with testing_session() as db:
        original = db.get(PublishJob, 1)
        retry = db.get(PublishJob, 2)
        retry_audit = (
            db.query(AuditEvent).filter(AuditEvent.action == "publish.retry_requested").one()
        )
        assert original.status == PublishJobStatus.BLOCKED
        assert retry.status == PublishJobStatus.PUBLISHED
        assert retry.meli_item_id == "MLM999"
        assert retry.request_summary_json["review_provider"] == "claude"
        assert retry_audit.entity_id == "1"
        assert retry_audit.after_json["retry_store_id"] == 1


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
