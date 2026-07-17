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
from app.models.product_draft_approval import ProductDraftApproval
from app.models.registry import import_all_models
from app.models.review_result import ReviewDecision, ReviewResult
from app.models.store import Store
from app.models.token_credential import TokenCredential
from app.schemas.publishing import PublishExecutionResult
from app.services.meli.token_vault import encrypt_token_value


def make_client(with_config: bool = True):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    import_all_models()
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    with testing_session() as db:
        db.add(MeliMetadataCache(cache_key="category_attributes:MLM123", payload_json={"attributes": []}))
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
                title="Bottle",
                description="Leak proof.",
                target_site_id="MLM",
                target_category_id="",
                price=9.99,
                currency="MXN",
                stock=2,
                image_urls_json=["https://example.com/a.jpg"],
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
    client = TestClient(app)
    if with_config:
        client.put(
            "/api/drafts/1/listing-config",
            json={
                "site_id": "MLM",
                "category_id": "MLM123",
                "listing_type_id": "gold_special",
                "fulfillment": "not_full",
                "attributes": [],
            },
        )
    return client, testing_session


def teardown_function():
    app.dependency_overrides.clear()


def review_payload():
    return {
        "provider": "local_policy",
        "decision": "pass",
        "risk_level": "low",
        "reason_codes": [],
        "reasons": [],
        "suggested_changes": {},
    }


def seed_publish_review(testing_session) -> int:
    with testing_session() as db:
        draft = db.get(ProductDraft, 1)
        row = ReviewResult(
            product_draft_id=1,
            provider="claude+nvidia_behavioral_audit",
            risk_level="low",
            decision=ReviewDecision.PASS,
            reasons_json={"reason_codes": [], "reasons": []},
            suggested_changes_json={},
            draft_version=draft.content_version,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.id


def publish_from_draft_payload(review_result_id: int):
    return {
        "store_id": 1,
        "product_draft_id": 1,
        "review": review_payload() | {"review_result_id": review_result_id},
        "valid_listing_type_ids": ["gold_special"],
        "human_approved": True,
    }


def test_draft_can_be_approved_and_audited():
    client, testing_session = make_client()
    seed_publish_review(testing_session)

    response = client.post(
        "/api/drafts/1/approval",
        json={"approved_by": "operator", "note": "checked listing"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["product_draft_id"] == 1
    assert body["approved_by"] == "operator"
    assert body["status"] == "approved"
    with testing_session() as db:
        approval = db.query(ProductDraftApproval).one()
        assert approval.note == "checked listing"
        event = db.query(AuditEvent).filter(AuditEvent.action == "draft.approved").one()
        assert event.entity_type == "product_draft"
        assert event.entity_id == "1"
        assert event.after_json["approved_by"] == "operator"


def test_draft_approval_requires_current_claude_nvidia_pass():
    client, testing_session = make_client()

    response = client.post(
        "/api/drafts/1/approval",
        json={"approved_by": "operator"},
    )

    assert response.status_code == 422
    assert "current_claude_nvidia_pass_required_before_approval" in response.text
    with testing_session() as db:
        assert db.query(ProductDraftApproval).count() == 0


def test_execute_from_draft_ignores_request_boolean_without_saved_approval(monkeypatch):
    async def fake_execute_publish(**kwargs):
        raise AssertionError("publish adapter should not run without saved approval")

    monkeypatch.setattr(publishing.settings, "token_encryption_key", "test-secret")
    monkeypatch.setattr(publishing.settings, "allow_live_publish", True)
    monkeypatch.setattr(publishing, "execute_publish", fake_execute_publish)
    client, testing_session = make_client()
    review_result_id = seed_publish_review(testing_session)

    response = client.post(
        "/api/publishing/execute-from-draft",
        json=publish_from_draft_payload(review_result_id),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "blocked"
    assert "human_approval_required" in body["errors"]


def test_execute_from_draft_uses_saved_approval(monkeypatch):
    async def fake_execute_publish(**kwargs):
        assert kwargs["human_approved"] is True
        return PublishExecutionResult(status="published", item_id="MLM123")

    monkeypatch.setattr(publishing.settings, "token_encryption_key", "test-secret")
    monkeypatch.setattr(publishing.settings, "allow_live_publish", True)
    monkeypatch.setattr(publishing, "execute_publish", fake_execute_publish)
    client, testing_session = make_client()
    review_result_id = seed_publish_review(testing_session)
    client.post("/api/drafts/1/approval", json={"approved_by": "operator"})

    response = client.post(
        "/api/publishing/execute-from-draft",
        json=publish_from_draft_payload(review_result_id) | {"human_approved": False},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "published"
