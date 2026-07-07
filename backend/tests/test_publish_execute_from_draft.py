from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import publishing
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.product_draft import ProductDraft
from app.models.publish_job import PublishJob, PublishJobStatus
from app.models.registry import import_all_models
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
                currency="USD",
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
                "attributes": [{"id": "BRAND", "value_name": "Acme"}],
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


def execute_payload():
    return {
        "store_id": 1,
        "product_draft_id": 1,
        "review": review_payload(),
        "valid_listing_type_ids": ["gold_special"],
        "human_approved": True,
    }


def test_publish_execute_from_draft_uses_saved_config_and_persists_job(monkeypatch):
    async def fake_execute_publish(**kwargs):
        assert kwargs["client"].access_token == "access-token"
        assert kwargs["draft"].target_category_id == "MLM123"
        assert kwargs["listing_choice"].listing_type_id == "gold_special"
        assert kwargs["listing_choice"].attributes == [{"id": "BRAND", "value_name": "Acme"}]
        return PublishExecutionResult(
            status="published",
            item_id="MLM999",
            permalink="https://example.com/MLM999",
        )

    monkeypatch.setattr(publishing.settings, "allow_live_publish", True)
    monkeypatch.setattr(publishing.settings, "token_encryption_key", "test-secret")
    monkeypatch.setattr(publishing, "execute_publish", fake_execute_publish)
    client, testing_session = make_client()
    client.post("/api/drafts/1/approval", json={"approved_by": "operator"})

    response = client.post("/api/publishing/execute-from-draft", json=execute_payload())

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
    monkeypatch.setattr(publishing.settings, "token_encryption_key", "test-secret")
    client, testing_session = make_client()

    response = client.post("/api/publishing/enqueue-from-draft", json=execute_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == 1
    assert body["status"] == "pending"
    assert body["product_draft_id"] == 1
    assert body["store_id"] == 1
    with testing_session() as db:
        job = db.query(PublishJob).one()
        assert job.status == PublishJobStatus.PENDING
        assert job.request_summary_json["review_provider"] == "local_policy"
        assert job.request_summary_json["listing_type_id"] == "gold_special"


def test_publish_execute_from_draft_requires_saved_config(monkeypatch):
    monkeypatch.setattr(publishing.settings, "token_encryption_key", "test-secret")
    client, _ = make_client(with_config=False)

    response = client.post("/api/publishing/execute-from-draft", json=execute_payload())

    assert response.status_code == 404
    assert "Listing config not found" in response.text
