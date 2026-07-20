import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.product_draft import ProductDraft
from app.models.publish_job import PublishJob, PublishJobStatus
from app.models.registry import import_all_models
from app.models.review_result import ReviewDecision, ReviewResult
from app.models.store import Store
from app.models.meli_metadata_cache import MeliMetadataCache
from app.models.token_credential import TokenCredential
from app.schemas.publishing import PublishExecutionResult
from app.services.meli.token_vault import encrypt_token_value
from app.workers.publish_worker import run_pending_publish_jobs


AMAZON_HTML = """
<html>
  <input id="ASIN" value="B000TEST01" />
  <span id="productTitle"> TrailPro Stainless Bottle </span>
  <span class="a-price"><span class="a-offscreen">$19.99</span></span>
  <div id="bylineInfo">Brand: TrailPro</div>
  <div id="feature-bullets"><ul><li>Leak proof lid</li></ul></div>
  <div id="productDescription"><p>Keeps drinks cold.</p></div>
  <img id="landingImage" src="https://example.com/main.jpg" />
</html>
"""


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
        db.add(MeliMetadataCache(cache_key="category_attributes:MLM123", payload_json={"attributes": []}))
        store = Store(
            site_id="MLM",
            seller_id="seller-e2e",
            display_name="E2E Store",
            oauth_status="connected",
            token_reference="meli:seller-e2e",
        )
        db.add(store)
        db.flush()
        db.add(
            TokenCredential(
                store_id=store.id,
                token_reference=store.token_reference,
                encrypted_access_token=encrypt_token_value("e2e-access-token", "e2e-secret"),
                encrypted_refresh_token=encrypt_token_value("e2e-refresh-token", "e2e-secret"),
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


def seed_publish_review(testing_session, draft_id: int) -> dict:
    with testing_session() as db:
        draft = db.get(ProductDraft, draft_id)
        row = ReviewResult(
            product_draft_id=draft_id,
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
        return {
            "provider": row.provider,
            "decision": "pass",
            "risk_level": "low",
            "reason_codes": [],
            "reasons": [],
            "suggested_changes": {},
            "review_result_id": row.id,
        }


@pytest.mark.asyncio
async def test_amazon_to_pre_listing_queue_and_worker_flow():
    client, testing_session = make_client()

    imported = client.post(
        "/api/imports/amazon-html",
        json={
            "source_url": "https://www.amazon.com/dp/B000TEST01",
            "html": AMAZON_HTML,
            "target_site_id": "MLM",
            "persist": True,
        },
    )
    assert imported.status_code == 200
    draft_id = imported.json()["id"]
    assert imported.json()["draft"]["title"] == "TrailPro Stainless Bottle"

    priced = client.put(
        f"/api/drafts/{draft_id}/pricing",
        json={
            "source_price": imported.json()["draft"]["source_price"],
            "source_currency": imported.json()["draft"]["source_currency"],
            "target_currency": "MXN",
            "exchange_rate": 18,
            "shipping_cost": 60,
            "platform_fee_rate": 0.15,
            "profit_margin_rate": 0.2,
            "rounding_increment": 10,
        },
    )
    assert priced.status_code == 200
    configured = client.put(
        f"/api/drafts/{draft_id}/listing-config",
        json={
            "site_id": "MLM",
            "category_id": "MLM123",
            "listing_type_id": "gold_pro",
            "fulfillment": "not_full",
            "attributes": [{"id": "BRAND", "value_name": "TrailPro"}],
        },
    )
    assert configured.status_code == 200
    assert configured.json()["fulfillment"] == "not_full"
    reviewed = seed_publish_review(testing_session, draft_id)

    approved = client.post(
        f"/api/drafts/{draft_id}/approval",
        json={"approved_by": "operator", "note": "E2E approved"},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    queued = client.post(
        "/api/publishing/enqueue-from-draft",
        json={
            "product_draft_id": draft_id,
            "store_id": 1,
            "review": reviewed,
            "valid_listing_type_ids": ["gold_pro"],
            "human_approved": False,
        },
    )
    assert queued.status_code == 200
    assert queued.json()["status"] == "pending"

    async def fake_publisher(**kwargs):
        assert kwargs["client"].access_token == "e2e-access-token"
        assert kwargs["listing_choice"].listing_type_id == "gold_pro"
        assert kwargs["listing_choice"].fulfillment == "not_full"
        assert kwargs["review"].decision == "pass"
        return PublishExecutionResult(status="published", item_id="MLM-E2E-1")

    with testing_session() as db:
        summary = await run_pending_publish_jobs(
            db,
            limit=10,
            publisher=fake_publisher,
            allow_live_publish=True,
            token_encryption_key="e2e-secret",
        )

    assert summary == {"processed": 1, "published": 1, "blocked": 0, "failed": 0, "recovered": 0}
    with testing_session() as db:
        job = db.query(PublishJob).one()
        assert job.status == PublishJobStatus.PUBLISHED
        assert job.meli_item_id == "MLM-E2E-1"
        assert db.query(ProductDraft).one().target_site_id == "MLM"


def test_full_fulfillment_is_rejected_before_queueing():
    client, _ = make_client()
    imported = client.post(
        "/api/imports/amazon-html",
        json={"source_url": "https://www.amazon.com/dp/B000TEST01", "html": AMAZON_HTML, "persist": True},
    )
    draft_id = imported.json()["id"]

    response = client.put(
        f"/api/drafts/{draft_id}/listing-config",
        json={
            "site_id": "MLM",
            "category_id": "MLM123",
            "listing_type_id": "gold_special",
            "fulfillment": "FULL",
            "attributes": [],
        },
    )

    assert response.status_code == 422
    assert "FULL fulfillment is excluded" in response.text


def test_selected_site_requires_matching_authorized_store_before_queueing():
    client, testing_session = make_client()
    imported = client.post(
        "/api/imports/amazon-html",
        json={
            "source_url": "https://www.amazon.com/dp/B000TEST01",
            "html": AMAZON_HTML,
            "persist": True,
        },
    )
    draft_id = imported.json()["id"]
    configured = client.put(
        f"/api/drafts/{draft_id}/listing-config",
        json={
            "site_id": "MLA",
            "category_id": "MLA123",
            "listing_type_id": "gold_special",
            "fulfillment": "not_full",
            "attributes": [],
        },
    )
    assert configured.status_code == 200
    reviewed = seed_publish_review(testing_session, draft_id)
    client.post(f"/api/drafts/{draft_id}/approval", json={"approved_by": "operator"})

    response = client.post(
        "/api/publishing/enqueue-from-draft",
        json={
            "product_draft_id": draft_id,
            "store_id": 1,
            "review": reviewed,
            "valid_listing_type_ids": ["gold_special"],
            "human_approved": True,
        },
    )

    assert response.status_code == 422
    assert "store_site_mismatch" in response.text
