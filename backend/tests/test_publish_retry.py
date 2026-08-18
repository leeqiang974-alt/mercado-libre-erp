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
                payload_json={"attributes": [{"id": "BRAND", "tags": {}}, {"id": "ITEM_CONDITION", "value_type": "list", "values": [{"id": "2230284", "name": "New"}], "tags": {"hidden": True}}], "verified": True},
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
                available_quantity=2,
                attributes_json=[{"id": "ITEM_CONDITION", "value_id": "2230284", "value_name": "New"}, {"id": "BRAND", "value_name": "Demo"}],
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
                prompt_version="meli-behavioral-audit-v4",
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
        "publish_reference": "amp-0123456789abcdef0123456789abcdef",
        "title": "Persisted Bottle",
        "description": "Leak proof.",
        "site_id": "MLM",
        "category_id": "MLM123",
        "listing_type_id": "gold_special",
        "shipping_mode": "me2",
        "shipping_logistic_type": "drop_off",
        "review_provider": "claude+nvidia_behavioral_audit",
        "review_result_id": 1,
        "review_decision": "pass",
        "review_risk_level": "low",
        "review_reason_codes": [],
        "review_reasons": [],
        "review_suggested_changes": {},
    }


def seed_unknown_publish_job(testing_session):
    with testing_session() as db:
        db.add(
            PublishJob(
                product_draft_id=1,
                store_id=1,
                requested_by="operator",
                status=PublishJobStatus.BLOCKED,
                request_summary_json=job_summary(),
                response_summary_json={
                    "status": "blocked",
                    "errors": [
                        "publish_outcome_unknown_manual_reconciliation_required"
                    ],
                },
            )
        )
        db.commit()


def reconciled_item(**updates):
    return {
        "id": "MLM999",
        "seller_id": "seller-1",
        "seller_custom_field": "amp-0123456789abcdef0123456789abcdef",
        "site_id": "MLM",
        "category_id": "MLM123",
        "listing_type_id": "gold_special",
        "status": "active",
        "permalink": "https://example.com/MLM999",
        "shipping": {"mode": "me2", "logistic_type": "drop_off"},
    } | updates


def test_unknown_publish_job_reconciles_one_exact_item(monkeypatch):
    async def fake_get(self, path):
        assert self.access_token == "access-token"
        if path.startswith("/users/seller-1/items/search?sku="):
            return {"results": ["MLM999"], "paging": {"total": 1}}
        if path == "/items/MLM999":
            return reconciled_item()
        assert path == "/items/MLM999/description"
        return {"plain_text": "Leak proof."}

    async def fake_post(self, path, payload):
        raise AssertionError("An already matching description must not be posted again.")

    monkeypatch.setattr(publishing.settings, "token_encryption_key", "test-secret")
    monkeypatch.setattr(publishing.MercadoLibreClient, "get", fake_get)
    monkeypatch.setattr(publishing.MercadoLibreClient, "post", fake_post)
    client, testing_session = make_client()
    seed_unknown_publish_job(testing_session)

    response = client.post("/api/publishing/jobs/1/reconcile")

    assert response.status_code == 200
    assert response.json()["status"] == "published"
    assert response.json()["item_id"] == "MLM999"
    with testing_session() as db:
        job = db.get(PublishJob, 1)
        assert job.status == PublishJobStatus.PUBLISHED
        assert job.meli_item_id == "MLM999"
        event = db.query(AuditEvent).filter(AuditEvent.action == "publish.reconciled").one()
        assert event.after_json["match_count"] == 1


def test_unknown_publish_reconciliation_keeps_zero_or_multiple_matches_blocked(
    monkeypatch,
):
    results = []

    async def fake_get(self, path):
        assert path.startswith("/users/seller-1/items/search?sku=")
        return {"results": results, "paging": {"total": len(results)}}

    monkeypatch.setattr(publishing.settings, "token_encryption_key", "test-secret")
    monkeypatch.setattr(publishing.MercadoLibreClient, "get", fake_get)
    client, testing_session = make_client()
    seed_unknown_publish_job(testing_session)

    no_match = client.post("/api/publishing/jobs/1/reconcile")
    results.extend(["MLM999", "MLM998"])
    multiple = client.post("/api/publishing/jobs/1/reconcile")

    assert no_match.status_code == 200
    assert no_match.json()["errors"] == [
        "publish_outcome_unknown_manual_reconciliation_required",
        "publish_reconciliation_no_match",
    ]
    assert multiple.status_code == 200
    assert multiple.json()["errors"] == [
        "publish_outcome_unknown_manual_reconciliation_required",
        "publish_reconciliation_multiple_matches",
    ]
    with testing_session() as db:
        assert db.get(PublishJob, 1).status == PublishJobStatus.BLOCKED


def test_unknown_publish_reconciliation_closes_mismatched_item(monkeypatch):
    async def fake_get(self, path):
        if path.startswith("/users/seller-1/items/search?sku="):
            return {"results": ["MLM999"], "paging": {"total": 1}}
        return reconciled_item(listing_type_id="gold_pro")

    async def fake_put(self, path, payload):
        assert path == "/items/MLM999"
        assert payload == {"status": "closed"}
        return {"status": "closed"}

    monkeypatch.setattr(publishing.settings, "token_encryption_key", "test-secret")
    monkeypatch.setattr(publishing.MercadoLibreClient, "get", fake_get)
    monkeypatch.setattr(publishing.MercadoLibreClient, "put", fake_put)
    client, testing_session = make_client()
    seed_unknown_publish_job(testing_session)

    response = client.post("/api/publishing/jobs/1/reconcile")

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert response.json()["item_id"] == "MLM999"
    assert response.json()["errors"] == ["meli_publish_listing_type_mismatch"]


def test_unknown_publish_reconciliation_closes_item_when_shipping_changed(monkeypatch):
    async def fake_get(self, path):
        if path.startswith("/users/seller-1/items/search?sku="):
            return {"results": ["MLM999"], "paging": {"total": 1}}
        return reconciled_item(
            shipping={"mode": "me2", "logistic_type": "self_service"}
        )

    async def fake_put(self, path, payload):
        assert path == "/items/MLM999"
        assert payload == {"status": "closed"}
        return {"status": "closed"}

    monkeypatch.setattr(publishing.settings, "token_encryption_key", "test-secret")
    monkeypatch.setattr(publishing.MercadoLibreClient, "get", fake_get)
    monkeypatch.setattr(publishing.MercadoLibreClient, "put", fake_put)
    client, testing_session = make_client()
    seed_unknown_publish_job(testing_session)

    response = client.post("/api/publishing/jobs/1/reconcile")

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert response.json()["errors"] == ["meli_publish_logistic_type_mismatch"]


def test_unknown_publish_reconciliation_rejects_legacy_job_without_reference(monkeypatch):
    monkeypatch.setattr(publishing.settings, "token_encryption_key", "test-secret")
    client, testing_session = make_client()
    seed_unknown_publish_job(testing_session)
    with testing_session() as db:
        job = db.get(PublishJob, 1)
        job.request_summary_json = {"site_id": "MLM"}
        db.commit()

    response = client.post("/api/publishing/jobs/1/reconcile")

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "Publish job predates searchable reconciliation references."
    )


def test_unknown_publish_reconciliation_keeps_unknown_when_token_is_missing(
    monkeypatch,
):
    async def no_token(**kwargs):
        return ""

    monkeypatch.setattr(publishing.settings, "token_encryption_key", "test-secret")
    monkeypatch.setattr(publishing, "resolve_fresh_store_access_token", no_token)
    client, testing_session = make_client()
    seed_unknown_publish_job(testing_session)

    response = client.post("/api/publishing/jobs/1/reconcile")
    retry = client.post("/api/publishing/jobs/1/retry")

    assert response.status_code == 200
    assert response.json()["errors"] == [
        "publish_outcome_unknown_manual_reconciliation_required",
        "store_access_token_required",
    ]
    assert retry.status_code == 409


def test_unknown_publish_reconciliation_uses_search_total_not_first_page(monkeypatch):
    async def fake_get(self, path):
        assert path.startswith("/users/seller-1/items/search?sku=")
        return {"results": ["MLM999"], "paging": {"total": 2}}

    monkeypatch.setattr(publishing.settings, "token_encryption_key", "test-secret")
    monkeypatch.setattr(publishing.MercadoLibreClient, "get", fake_get)
    client, testing_session = make_client()
    seed_unknown_publish_job(testing_session)

    response = client.post("/api/publishing/jobs/1/reconcile")

    assert response.status_code == 200
    assert response.json()["errors"] == [
        "publish_outcome_unknown_manual_reconciliation_required",
        "publish_reconciliation_multiple_matches",
    ]


def test_unknown_publish_reconciliation_never_closes_unconfirmed_identity(monkeypatch):
    async def fake_get(self, path):
        if path.startswith("/users/seller-1/items/search?sku="):
            return {"results": ["MLM999"], "paging": {"total": 1}}
        assert path == "/items/MLM999"
        return reconciled_item(seller_custom_field="someone-elses-reference")

    async def unexpected_put(self, path, payload):
        raise AssertionError("An item with unconfirmed identity must never be closed.")

    monkeypatch.setattr(publishing.settings, "token_encryption_key", "test-secret")
    monkeypatch.setattr(publishing.MercadoLibreClient, "get", fake_get)
    monkeypatch.setattr(publishing.MercadoLibreClient, "put", unexpected_put)
    client, testing_session = make_client()
    seed_unknown_publish_job(testing_session)

    response = client.post("/api/publishing/jobs/1/reconcile")

    assert response.status_code == 200
    assert response.json()["status"] == "blocked"
    assert response.json()["item_id"] == "MLM999"
    assert response.json()["errors"] == [
        "meli_publish_reference_mismatch",
        "publish_outcome_unknown_manual_reconciliation_required",
    ]


def test_unknown_publish_reconciliation_rejects_mismatched_item_response_id(monkeypatch):
    async def fake_get(self, path):
        assert path == "/items/MLM999"
        return reconciled_item(id="MLM998")

    async def unexpected_put(self, path, payload):
        raise AssertionError("A mismatched response item must never be closed.")

    monkeypatch.setattr(publishing.settings, "token_encryption_key", "test-secret")
    monkeypatch.setattr(publishing.MercadoLibreClient, "get", fake_get)
    monkeypatch.setattr(publishing.MercadoLibreClient, "put", unexpected_put)
    client, testing_session = make_client()
    seed_unknown_publish_job(testing_session)
    with testing_session() as db:
        job = db.get(PublishJob, 1)
        job.meli_item_id = "MLM999"
        db.commit()

    response = client.post("/api/publishing/jobs/1/reconcile")

    assert response.status_code == 200
    assert response.json()["status"] == "blocked"
    assert response.json()["item_id"] == ""
    assert response.json()["errors"] == [
        "meli_publish_item_id_mismatch",
        "publish_outcome_unknown_manual_reconciliation_required",
    ]
    with testing_session() as db:
        assert db.get(PublishJob, 1).meli_item_id == ""


def test_unknown_publish_reconciliation_rejects_superseded_lease(monkeypatch):
    async def fake_get(self, path):
        if path.startswith("/users/seller-1/items/search?sku="):
            return {"results": ["MLM999"], "paging": {"total": 1}}
        if path == "/items/MLM999":
            with testing_session() as concurrent_db:
                job = concurrent_db.get(PublishJob, 1)
                job.response_summary_json = {
                    "status": "validating",
                    "errors": [
                        "publish_outcome_unknown_manual_reconciliation_required"
                    ],
                    "reconciliation_lease": "newer-attempt",
                }
                concurrent_db.commit()
            return reconciled_item()
        return {"plain_text": "Leak proof."}

    monkeypatch.setattr(publishing.settings, "token_encryption_key", "test-secret")
    monkeypatch.setattr(publishing.MercadoLibreClient, "get", fake_get)
    client, testing_session = make_client()
    seed_unknown_publish_job(testing_session)

    response = client.post("/api/publishing/jobs/1/reconcile")

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "Publish reconciliation was superseded by a newer attempt."
    )


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
                prompt_version="meli-behavioral-audit-v4",
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
