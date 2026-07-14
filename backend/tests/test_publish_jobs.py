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
from app.models.publish_job import PublishJob, PublishJobStatus
from app.models.registry import import_all_models
from app.models.store import Store
from app.models.token_credential import TokenCredential
from app.schemas.publishing import PublishExecutionResult
from app.services.meli.token_vault import encrypt_token_value


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
        db.add(
            ProductDraft(
                title="Persisted Bottle",
                target_site_id="MLM",
                target_category_id="MLM123",
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
            "currency": "USD",
            "stock": 2,
            "image_urls": ["https://example.com/a.jpg"],
        },
        "review": {
            "provider": "local_policy",
            "decision": "pass",
            "risk_level": "low",
            "reason_codes": [],
            "reasons": [],
            "suggested_changes": {},
        },
        "listing_choice": {
            "site_id": "MLM",
            "listing_type_id": "gold_special",
            "fulfillment": "not_full",
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


def test_publish_execute_blocks_when_draft_site_does_not_match_authorized_store(monkeypatch):
    monkeypatch.setattr(publishing.settings, "allow_live_publish", True)
    monkeypatch.setattr(publishing.settings, "token_encryption_key", "test-secret")

    async def unexpected_publish(**kwargs):
        raise AssertionError("site mismatch must block before the publisher")

    monkeypatch.setattr(publishing, "execute_publish", unexpected_publish)
    client, testing_session = make_client()
    body = payload()
    body["draft"]["target_site_id"] = "MLA"
    body["listing_choice"]["site_id"] = "MLA"

    response = client.post("/api/publishing/execute", json=body)

    assert response.status_code == 200
    assert response.json()["status"] == "blocked"
    assert "store_site_mismatch" in response.json()["errors"]
    with testing_session() as db:
        assert db.query(PublishJob).one().status == PublishJobStatus.BLOCKED


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
