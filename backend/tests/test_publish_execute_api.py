from fastapi.testclient import TestClient
import httpx
from datetime import UTC, datetime, timedelta

from app.api.routes import publishing
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.registry import import_all_models
from app.models.draft_listing_config import DraftListingConfig
from app.models.product_draft import ProductDraft
from app.models.meli_metadata_cache import MeliMetadataCache
from app.models.product_draft_approval import ProductDraftApproval
from app.models.review_result import ReviewDecision, ReviewResult
from app.models.store import Store
from app.models.token_credential import TokenCredential
from app.schemas.publishing import PublishExecutionResult
from app.services.meli.oauth import MercadoLibreOAuthClient
from app.services.meli.token_vault import encrypt_token_value
from pricing_test_support import add_current_pricing
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def payload():
    return {
        "store_id": 1,
        "product_draft_id": 1,
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
    }


def make_client(with_store: bool = True, token_expires_in_seconds: int = 7200):
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
        if with_store:
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
                    store_id=store.id if with_store else None,
                    token_reference="meli:seller-1",
                    encrypted_access_token=encrypt_token_value("access-token", "test-secret"),
                    encrypted_refresh_token=encrypt_token_value("refresh-token", "test-secret"),
                    expires_at=datetime.now(UTC) + timedelta(seconds=token_expires_in_seconds),
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
                    store_id=store.id if with_store else None,
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
    return TestClient(app)


def teardown_function():
    app.dependency_overrides.clear()


def test_publish_execute_route_blocks_by_default(monkeypatch):
    monkeypatch.setattr(publishing.settings, "token_encryption_key", "test-secret")
    client = make_client()
    response = client.post("/api/publishing/execute", json=payload())

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "blocked"
    assert "live_publish_disabled" in body["errors"]
    assert "meli:seller-1" not in response.text


def test_publish_execute_route_uses_store_token_reference_without_echoing_it(monkeypatch):
    async def fake_execute_publish(**kwargs):
        assert kwargs["client"].access_token == "access-token"
        return PublishExecutionResult(
            status="published",
            item_id="MLM123",
            permalink="https://example.com/MLM123",
        )

    monkeypatch.setattr(publishing.settings, "allow_live_publish", True)
    monkeypatch.setattr(publishing.settings, "token_encryption_key", "test-secret")
    monkeypatch.setattr(publishing, "execute_publish", fake_execute_publish)
    client = make_client()

    response = client.post("/api/publishing/execute", json=payload())

    assert response.status_code == 200
    assert response.json()["item_id"] == "MLM123"
    assert "meli:seller-1" not in response.text


def test_publish_execute_route_refreshes_expiring_store_token(monkeypatch):
    async def fake_execute_publish(**kwargs):
        assert kwargs["client"].access_token == "new-access-token"
        return PublishExecutionResult(
            status="published",
            item_id="MLM123",
            permalink="https://example.com/MLM123",
        )

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "access_token": "new-access-token",
                "refresh_token": "new-refresh-token",
                "expires_in": 21600,
                "user_id": "seller-1",
            },
        )

    def fake_oauth_client(db=None) -> MercadoLibreOAuthClient:
        return MercadoLibreOAuthClient(
            client_id="client-123",
            client_secret="secret-456",
            redirect_uri="http://localhost:8000/api/stores/meli/callback",
            transport=httpx.MockTransport(handler),
        )

    monkeypatch.setattr(publishing.settings, "allow_live_publish", True)
    monkeypatch.setattr(publishing.settings, "token_encryption_key", "test-secret")
    monkeypatch.setattr(publishing, "execute_publish", fake_execute_publish)
    monkeypatch.setattr(publishing, "create_oauth_client", fake_oauth_client)
    client = make_client(token_expires_in_seconds=30)

    response = client.post("/api/publishing/execute", json=payload())

    assert response.status_code == 200
    assert response.json()["item_id"] == "MLM123"
    assert "new-access-token" not in response.text
    assert "new-refresh-token" not in response.text


def test_publish_execute_route_invalidates_review_for_unknown_store():
    client = make_client(with_store=False)

    response = client.post("/api/publishing/execute", json=payload())

    assert response.status_code == 422
    assert response.json()["detail"] == "latest_behavioral_review_required"
