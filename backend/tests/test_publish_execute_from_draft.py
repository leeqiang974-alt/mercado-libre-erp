import httpx
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import publishing
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.audit_event import AuditEvent
from app.models.draft_pricing_config import DraftPricingConfig
from app.models.product_draft import ProductDraft
from app.models.meli_metadata_cache import MeliMetadataCache
from app.models.publish_job import PublishJob, PublishJobStatus
from app.models.registry import import_all_models
from app.models.review_result import ReviewDecision, ReviewResult
from app.models.store import Store
from app.models.token_credential import TokenCredential
from app.schemas.publishing import PublishExecutionResult
from app.services.meli.token_vault import encrypt_token_value
from pricing_test_support import add_current_pricing


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
        db.add(
            MeliMetadataCache(
                cache_key="category_attributes:MLM123",
                payload_json={
                    "attributes": [
                        {"id": "BRAND", "tags": {}},
                        {
                            "id": "ITEM_CONDITION",
                            "value_type": "list",
                            "values": [{"id": "2230284", "name": "New"}],
                            "tags": {"hidden": True},
                        },
                    ],
                    "verified": True,
                },
            )
        )
        db.add(MeliMetadataCache(
            cache_key="available_listing_types:1:MLM123",
            payload_json={"store_id": 1, "category_id": "MLM123", "listing_types": [{"id": "gold_special"}, {"id": "gold_pro"}], "verified": True},
        ))
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
            target_category_id="",
            price=9.99,
            currency="MXN",
            stock=2,
            image_urls_json=["https://example.com/a.jpg"],
        )
        db.add(draft)
        db.flush()
        add_current_pricing(db, draft)
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
                "store_id": 1,
                "category_id": "MLM123",
                "listing_type_id": "gold_special",
                "fulfillment": "not_full",
                "shipping_mode": "me2",
                "shipping_logistic_type": "drop_off",
                "available_quantity": 2,
                "attributes": [
                    {"id": "ITEM_CONDITION", "value_id": "2230284", "value_name": "New"},
                    {"id": "BRAND", "value_name": "Acme"},
                ],
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
            prompt_version="meli-behavioral-audit-v4",
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


def execute_payload(review_result_id: int):
    return {
        "store_id": 1,
        "product_draft_id": 1,
        "review": review_payload() | {"review_result_id": review_result_id},
        "valid_listing_type_ids": ["gold_special"],
        "human_approved": True,
    }


def test_publish_execute_from_draft_uses_saved_config_and_persists_job(monkeypatch):
    async def fake_execute_publish(**kwargs):
        assert kwargs["client"].access_token == "access-token"
        assert kwargs["draft"].target_category_id == "MLM123"
        assert kwargs["listing_choice"].listing_type_id == "gold_special"
        assert kwargs["listing_choice"].attributes == [
            {"id": "ITEM_CONDITION", "value_name": "New", "value_id": "2230284"},
            {"id": "BRAND", "value_name": "Acme"},
        ]
        return PublishExecutionResult(
            status="published",
            item_id="MLM999",
            permalink="https://example.com/MLM999",
        )

    monkeypatch.setattr(publishing.settings, "allow_live_publish", True)
    monkeypatch.setattr(publishing.settings, "token_encryption_key", "test-secret")
    monkeypatch.setattr(publishing, "execute_publish", fake_execute_publish)
    client, testing_session = make_client()
    review_result_id = seed_publish_review(testing_session)
    client.post("/api/drafts/1/approval", json={"approved_by": "operator"})

    response = client.post(
        "/api/publishing/execute-from-draft", json=execute_payload(review_result_id)
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "published"
    assert body["job_id"] == 1
    assert "access-token" not in response.text
    with testing_session() as db:
        job = db.query(PublishJob).one()
        assert job.product_draft_id == 1
        assert job.store_id == 1
        assert job.status == PublishJobStatus.PUBLISHED
        assert job.meli_item_id == "MLM999"


def test_publish_enqueue_from_draft_creates_pending_job(monkeypatch):
    async def shipping_preferences(self, path):
        assert self.access_token == "access-token"
        assert path == "/users/seller-1/shipping_preferences"
        return {
            "modes": ["me2"],
            "logistics": [{"mode": "me2", "types": [{"type": "drop_off"}]}],
        }

    monkeypatch.setattr(publishing.settings, "token_encryption_key", "test-secret")
    monkeypatch.setattr(publishing.MercadoLibreClient, "get", shipping_preferences)
    client, testing_session = make_client()
    review_result_id = seed_publish_review(testing_session)
    client.post("/api/drafts/1/approval", json={"approved_by": "operator"})

    response = client.post(
        "/api/publishing/enqueue-from-draft", json=execute_payload(review_result_id)
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == 1
    assert body["status"] == "pending"
    assert body["product_draft_id"] == 1
    assert body["store_id"] == 1
    with testing_session() as db:
        job = db.query(PublishJob).one()
        assert job.status == PublishJobStatus.PENDING
        assert job.request_summary_json["review_provider"] == "claude+nvidia_behavioral_audit"
        assert job.request_summary_json["listing_type_id"] == "gold_special"
        event = db.query(AuditEvent).filter(AuditEvent.action == "publish.queued").one()
        assert event.after_json["store_id"] == 1
        assert event.after_json["shipping_mode"] == "me2"
        assert event.after_json["shipping_logistic_type"] == "drop_off"


def test_publish_enqueue_from_draft_rejects_unapproved_job(monkeypatch):
    monkeypatch.setattr(publishing.settings, "token_encryption_key", "test-secret")
    client, testing_session = make_client()
    review_result_id = seed_publish_review(testing_session)

    response = client.post(
        "/api/publishing/enqueue-from-draft", json=execute_payload(review_result_id)
    )

    assert response.status_code == 422
    assert "human_approval_required" in response.text
    with testing_session() as db:
        assert db.query(PublishJob).count() == 0


def test_publish_execute_from_draft_requires_saved_config(monkeypatch):
    monkeypatch.setattr(publishing.settings, "token_encryption_key", "test-secret")
    client, _ = make_client(with_config=False)

    response = client.post("/api/publishing/execute-from-draft", json=execute_payload(999))

    assert response.status_code == 404
    assert "Listing config not found" in response.text


def test_publish_execute_from_draft_requires_saved_pricing(monkeypatch):
    async def unexpected_publish(**kwargs):
        raise AssertionError("missing pricing must block before the publisher")

    monkeypatch.setattr(publishing, "execute_publish", unexpected_publish)
    client, testing_session = make_client()
    review_result_id = seed_publish_review(testing_session)
    client.post("/api/drafts/1/approval", json={"approved_by": "operator"})
    with testing_session() as db:
        db.query(DraftPricingConfig).delete()
        db.commit()

    response = client.post(
        "/api/publishing/execute-from-draft", json=execute_payload(review_result_id)
    )

    assert response.status_code == 409
    assert response.json()["detail"] == {
        "code": "draft_pricing_not_ready",
        "errors": ["saved_pricing_required"],
    }
    with testing_session() as db:
        assert db.query(PublishJob).count() == 0


def test_publish_final_recheck_blocks_price_changed_after_job_creation(monkeypatch):
    async def mutate_draft_before_final_lock(**kwargs):
        with testing_session() as db:
            draft = db.get(ProductDraft, 1)
            draft.price = 10.99
            db.commit()
        return "access-token"

    async def unexpected_publish(**kwargs):
        raise AssertionError("stale pricing must block before the publisher")

    monkeypatch.setattr(publishing.settings, "allow_live_publish", True)
    monkeypatch.setattr(
        publishing,
        "resolve_fresh_store_access_token",
        mutate_draft_before_final_lock,
    )
    monkeypatch.setattr(publishing, "execute_publish", unexpected_publish)
    client, testing_session = make_client()
    review_result_id = seed_publish_review(testing_session)
    client.post("/api/drafts/1/approval", json={"approved_by": "operator"})

    response = client.post(
        "/api/publishing/execute-from-draft", json=execute_payload(review_result_id)
    )

    assert response.status_code == 200
    assert response.json()["status"] == "blocked"
    assert response.json()["errors"] == ["draft_price_not_from_saved_pricing"]
    with testing_session() as db:
        job = db.query(PublishJob).one()
        assert job.status == PublishJobStatus.BLOCKED


def test_publish_execute_replays_existing_result_without_duplicate_item(monkeypatch):
    calls = 0

    async def fake_execute_publish(**kwargs):
        nonlocal calls
        calls += 1
        return PublishExecutionResult(status="published", item_id="MLM-IDEMPOTENT")

    monkeypatch.setattr(publishing.settings, "allow_live_publish", True)
    monkeypatch.setattr(publishing.settings, "token_encryption_key", "test-secret")
    monkeypatch.setattr(publishing, "execute_publish", fake_execute_publish)
    client, testing_session = make_client()
    review_result_id = seed_publish_review(testing_session)
    client.post("/api/drafts/1/approval", json={"approved_by": "operator"})
    body = execute_payload(review_result_id)

    first = client.post("/api/publishing/execute-from-draft", json=body)
    second = client.post("/api/publishing/execute-from-draft", json=body)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["job_id"] == second.json()["job_id"]
    assert second.json()["item_id"] == "MLM-IDEMPOTENT"
    assert calls == 1
    with testing_session() as db:
        assert db.query(PublishJob).count() == 1
        assert (
            db.query(AuditEvent).filter(AuditEvent.action == "publish.idempotent_replay").count()
            == 1
        )


def test_shipping_change_invalidates_existing_review_and_approval(monkeypatch):
    monkeypatch.setattr(publishing.settings, "token_encryption_key", "test-secret")
    client, testing_session = make_client()
    review_result_id = seed_publish_review(testing_session)
    client.post("/api/drafts/1/approval", json={"approved_by": "operator"})
    changed = client.put(
        "/api/drafts/1/listing-config",
        json={
            "site_id": "MLM",
            "store_id": 1,
            "category_id": "MLM123",
            "listing_type_id": "gold_special",
            "fulfillment": "not_full",
                "shipping_mode": "me2",
                "shipping_logistic_type": "self_service",
                "available_quantity": 2,
                "attributes": [
                    {"id": "ITEM_CONDITION", "value_id": "2230284", "value_name": "New"},
                    {"id": "BRAND", "value_name": "Acme"},
                ],
        },
    )
    assert changed.status_code == 200

    response = client.post(
        "/api/publishing/execute-from-draft",
        json=execute_payload(review_result_id),
    )

    assert response.status_code == 422
    assert "review_for_stale_draft_version" in response.text


def test_preview_invalidates_review_when_store_disconnects_after_configuration(monkeypatch):
    monkeypatch.setattr(publishing.settings, "token_encryption_key", "test-secret")
    client, testing_session = make_client()
    review_result_id = seed_publish_review(testing_session)
    client.post("/api/drafts/1/approval", json={"approved_by": "operator"})
    with testing_session() as db:
        store = db.get(Store, 1)
        store.oauth_status = "disconnected"
        db.commit()

    response = client.post(
        "/api/publishing/preview-from-draft",
        json={
            "product_draft_id": 1,
            "review": review_payload() | {"review_result_id": review_result_id},
            "valid_listing_type_ids": ["gold_special"],
            "human_approved": True,
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "latest_behavioral_review_required"


def test_preview_blocks_shipping_selection_removed_from_store(monkeypatch):
    async def changed_shipping_preferences(self, path):
        return {
            "modes": ["me2"],
            "logistics": [{"mode": "me2", "types": [{"type": "self_service"}]}],
        }

    monkeypatch.setattr(publishing.settings, "token_encryption_key", "test-secret")
    monkeypatch.setattr(
        publishing.MercadoLibreClient,
        "get",
        changed_shipping_preferences,
    )
    client, testing_session = make_client()
    review_result_id = seed_publish_review(testing_session)
    client.post("/api/drafts/1/approval", json={"approved_by": "operator"})

    response = client.post(
        "/api/publishing/preview-from-draft",
        json={
            "product_draft_id": 1,
            "review": review_payload() | {"review_result_id": review_result_id},
            "valid_listing_type_ids": ["gold_special"],
            "human_approved": True,
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "allowed": False,
        "errors": ["selected_non_full_shipping_option_unavailable"],
    }


def test_enqueue_rejects_removed_shipping_without_creating_job(monkeypatch):
    async def changed_shipping_preferences(self, path):
        return {
            "modes": ["me2"],
            "logistics": [{"mode": "me2", "types": [{"type": "self_service"}]}],
        }

    async def unexpected_publish(**kwargs):
        raise AssertionError("enqueue preflight must never call /items")

    monkeypatch.setattr(publishing.settings, "token_encryption_key", "test-secret")
    monkeypatch.setattr(
        publishing.MercadoLibreClient,
        "get",
        changed_shipping_preferences,
    )
    monkeypatch.setattr(publishing, "execute_publish", unexpected_publish)
    client, testing_session = make_client()
    review_result_id = seed_publish_review(testing_session)
    client.post("/api/drafts/1/approval", json={"approved_by": "operator"})

    response = client.post(
        "/api/publishing/enqueue-from-draft",
        json=execute_payload(review_result_id),
    )

    assert response.status_code == 422
    assert "selected_non_full_shipping_option_unavailable" in response.text
    with testing_session() as db:
        assert db.query(PublishJob).count() == 0


def test_preview_reports_shipping_preferences_provider_failure(monkeypatch):
    async def failed_shipping_preferences(self, path):
        request = httpx.Request("GET", f"https://api.mercadolibre.com{path}")
        raise httpx.ConnectError("provider unavailable", request=request)

    monkeypatch.setattr(publishing.settings, "token_encryption_key", "test-secret")
    monkeypatch.setattr(
        publishing.MercadoLibreClient,
        "get",
        failed_shipping_preferences,
    )
    client, testing_session = make_client()
    review_result_id = seed_publish_review(testing_session)
    client.post("/api/drafts/1/approval", json={"approved_by": "operator"})

    response = client.post(
        "/api/publishing/preview-from-draft",
        json={
            "product_draft_id": 1,
            "review": review_payload() | {"review_result_id": review_result_id},
            "valid_listing_type_ids": ["gold_special"],
            "human_approved": True,
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "allowed": False,
        "errors": ["shipping_preferences_unavailable"],
    }


def test_generic_preview_rechecks_current_store_shipping(monkeypatch):
    async def changed_shipping_preferences(self, path):
        return {
            "modes": ["me2"],
            "logistics": [{"mode": "me2", "types": [{"type": "self_service"}]}],
        }

    monkeypatch.setattr(publishing.settings, "token_encryption_key", "test-secret")
    monkeypatch.setattr(
        publishing.MercadoLibreClient,
        "get",
        changed_shipping_preferences,
    )
    client, _ = make_client()

    response = client.post(
        "/api/publishing/preview",
        json={
            "draft": {
                "title": "Bottle",
                "description": "Leak proof.",
                "target_site_id": "MLM",
                "target_category_id": "MLM123",
                "price": 100,
                    "currency": "MXN",
                    "stock": 2,
                    "condition": "new",
                    "image_urls": ["https://example.com/a.jpg"],
            },
            "review": review_payload(),
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
        },
    )

    assert response.status_code == 200
    assert response.json()["allowed"] is False
    assert "selected_non_full_shipping_option_unavailable" in response.json()["errors"]


def test_enqueue_provider_failure_does_not_create_job(monkeypatch):
    async def failed_shipping_preferences(self, path):
        request = httpx.Request("GET", f"https://api.mercadolibre.com{path}")
        raise httpx.ConnectError("provider unavailable", request=request)

    monkeypatch.setattr(publishing.settings, "token_encryption_key", "test-secret")
    monkeypatch.setattr(
        publishing.MercadoLibreClient,
        "get",
        failed_shipping_preferences,
    )
    client, testing_session = make_client()
    review_result_id = seed_publish_review(testing_session)
    client.post("/api/drafts/1/approval", json={"approved_by": "operator"})

    response = client.post(
        "/api/publishing/enqueue-from-draft",
        json=execute_payload(review_result_id),
    )

    assert response.status_code == 422
    assert "shipping_preferences_unavailable" in response.text
    with testing_session() as db:
        assert db.query(PublishJob).count() == 0


def test_preview_reports_store_token_refresh_failure(monkeypatch):
    async def failed_token_refresh(*args, **kwargs):
        request = httpx.Request("POST", "https://api.mercadolibre.com/oauth/token")
        response = httpx.Response(401, request=request)
        raise httpx.HTTPStatusError("refresh rejected", request=request, response=response)

    monkeypatch.setattr(
        publishing,
        "resolve_fresh_store_access_token",
        failed_token_refresh,
    )
    client, testing_session = make_client()
    review_result_id = seed_publish_review(testing_session)
    client.post("/api/drafts/1/approval", json={"approved_by": "operator"})

    response = client.post(
        "/api/publishing/preview-from-draft",
        json={
            "product_draft_id": 1,
            "review": review_payload() | {"review_result_id": review_result_id},
            "valid_listing_type_ids": ["gold_special"],
            "human_approved": True,
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "allowed": False,
        "errors": ["store_token_refresh_unavailable"],
    }
