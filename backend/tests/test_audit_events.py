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
from app.models.product_draft_approval import ProductDraftApproval
from app.models.review_result import ReviewDecision, ReviewResult
from app.models.registry import import_all_models
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
            title="Bottle",
            description="Leak proof.",
            target_site_id="MLM",
            target_category_id="MLM123",
            price=9.99,
            currency="MXN",
            stock=2,
            listing_type_id="gold_special",
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


def draft_payload():
    return {
        "title": "Bottle",
        "description": "Leak proof.",
        "target_site_id": "MLM",
        "target_category_id": "MLM123",
        "price": 9.99,
        "currency": "MXN",
        "stock": 2,
        "listing_type_id": "gold_special",
        "image_urls": ["https://example.com/a.jpg"],
    }


def review_payload():
    return {
        "provider": "local_policy",
        "decision": "pass",
        "risk_level": "low",
        "reason_codes": [],
        "reasons": [],
        "suggested_changes": {},
    }


def execute_payload():
    return {
        "store_id": 1,
        "product_draft_id": 1,
        "draft": draft_payload(),
        "review": review_payload()
        | {"provider": "claude+nvidia_behavioral_audit", "review_result_id": 1},
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
    }


def test_persisted_review_creates_audit_event():
    client, testing_session = make_client()

    response = client.post("/api/reviews/local?product_draft_id=1", json=draft_payload())

    assert response.status_code == 200
    with testing_session() as db:
        event = db.query(AuditEvent).one()
        assert event.action == "review.completed"
        assert event.actor_type == "ai_provider"
        assert event.actor_id == "local_policy"
        assert event.entity_type == "product_draft"
        assert event.entity_id == "1"
        assert event.after_json["decision"] == "pass"


def test_publish_execute_creates_audit_event_and_can_be_listed(monkeypatch):
    async def fake_execute_publish(**kwargs):
        return PublishExecutionResult(
            status="published",
            item_id="MLM123",
            permalink="https://example.com/MLM123",
        )

    monkeypatch.setattr(publishing.settings, "allow_live_publish", True)
    monkeypatch.setattr(publishing.settings, "token_encryption_key", "test-secret")
    monkeypatch.setattr(publishing, "execute_publish", fake_execute_publish)
    client, testing_session = make_client()

    response = client.post("/api/publishing/execute", json=execute_payload())

    assert response.status_code == 200
    with testing_session() as db:
        event = db.query(AuditEvent).one()
        assert event.action == "publish.executed"
        assert event.actor_type == "operator"
        assert event.entity_type == "publish_job"
        assert event.entity_id == "1"
        assert event.after_json["status"] == "published"
        assert event.after_json["store_id"] == 1

    list_response = client.get("/api/audit-events")
    assert list_response.status_code == 200
    body = list_response.json()
    assert body[0]["action"] == "publish.executed"
    assert body[0]["after"]["item_id"] == "MLM123"
