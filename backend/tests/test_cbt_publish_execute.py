from datetime import UTC, datetime, timedelta

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import publishing
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.cbt_listing_config import CbtListingConfig
from app.models.meli_metadata_cache import MeliMetadataCache
from app.models.product_draft import ProductDraft
from app.models.product_draft_approval import ProductDraftApproval
from app.models.registry import import_all_models
from app.models.review_result import ReviewDecision, ReviewResult
from app.models.store import Store
from app.models.token_credential import TokenCredential
from app.services.meli.token_vault import encrypt_token_value


def test_global_publish_error_keeps_meli_validation_message():
    request = httpx.Request("POST", "https://api.mercadolibre.com/global/items")
    response = httpx.Response(
        400,
        request=request,
        json={
            "message": "Validation failed",
            "error": "validation_error",
            "cause": [{"code": "item.attributes.invalid", "message": "PACKAGE_WEIGHT is invalid"}],
        },
    )

    result = publishing._meli_global_publish_error(
        httpx.HTTPStatusError("bad request", request=request, response=response)
    )

    assert "meli_global_publish_failed:400" in result
    assert "PACKAGE_WEIGHT is invalid" in result


def make_client() -> TestClient:
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
            site_id="CBT",
            seller_id="2942677449",
            display_name="Global Selling Test Store",
            oauth_status="connected",
            token_reference="meli:2942677449",
        )
        db.add(store)
        db.flush()
        db.add(
            TokenCredential(
                store_id=store.id,
                token_reference=store.token_reference,
                encrypted_access_token=encrypt_token_value("access-token", "test-secret"),
                encrypted_refresh_token=encrypt_token_value("refresh-token", "test-secret"),
                expires_at=datetime.now(UTC) + timedelta(hours=2),
            )
        )
        draft = ProductDraft(
            title="Reusable Silicone Mold",
            description="English source description.",
            target_site_id="CBT",
            target_category_id="CBT432923",
            price=9.99,
            currency="USD",
            stock=10,
            image_urls_json=["https://example.com/source.jpg"],
            content_version=2,
        )
        db.add(draft)
        db.flush()
        db.add(
            CbtListingConfig(
                product_draft_id=draft.id,
                store_id=store.id,
                category_id="CBT432923",
                family_name="Silicone mold family",
                global_title=draft.title,
                description=draft.description,
                price_usd=9.99,
                available_quantity=10,
                attributes_json=[
                    {"id": "ITEM_CONDITION", "value_name": "New"},
                    {"id": "SELLER_SKU", "value_name": "SKU-100"},
                    {"id": "PACKAGE_HEIGHT", "value_name": "5 cm"},
                    {"id": "PACKAGE_LENGTH", "value_name": "10 cm"},
                    {"id": "PACKAGE_WIDTH", "value_name": "8 cm"},
                    {"id": "PACKAGE_WEIGHT", "value_name": "100 g"},
                ],
                sale_terms_json=[],
                sites_to_sell_json=[
                    {
                        "site_id": "MLM",
                        "title": "Molde de silicona reutilizable",
                        "listing_type_id": "gold_special",
                        "logistic_type": "remote",
                    }
                ],
                draft_content_version=2,
            )
        )
        db.add(
            MeliMetadataCache(
                cache_key="category_attributes:CBT432923",
                payload_json={
                    "verified": True,
                    "attributes": [
                        {"id": "ITEM_CONDITION", "tags": {}, "value_type": "text"},
                        {"id": "SELLER_SKU", "tags": {}},
                        {"id": "PACKAGE_HEIGHT", "tags": {}},
                        {"id": "PACKAGE_LENGTH", "tags": {}},
                        {"id": "PACKAGE_WIDTH", "tags": {}},
                        {"id": "PACKAGE_WEIGHT", "tags": {}},
                    ],
                },
            )
        )
        db.add(
            ReviewResult(
                id=1,
                product_draft_id=draft.id,
                provider="claude+nvidia_behavioral_audit",
                prompt_version="meli-behavioral-audit-v4",
                risk_level="low",
                decision=ReviewDecision.PASS,
                reasons_json={"reason_codes": [], "reasons": []},
                suggested_changes_json={},
                draft_version=2,
            )
        )
        db.add(
            ProductDraftApproval(
                product_draft_id=draft.id,
                status="approved",
                approved_by="operator",
                draft_version=2,
                review_result_id=1,
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
    return TestClient(app)


def teardown_function():
    app.dependency_overrides.clear()


def test_cbt_execute_posts_global_item_once_and_replays_idempotently(monkeypatch):
    calls: list[tuple[str, dict]] = []

    class FakeClient:
        def __init__(self, access_token: str):
            assert access_token == "access-token"

        async def get(self, path: str):
            assert path == "/users/me"
            return {"id": 2942677449, "site_id": "CBT", "tags": ["normal"]}

        async def post(self, path: str, payload: dict):
            calls.append((path, payload))
            return {"id": "CBT1000001", "permalink": "https://www.mercadolibre.com/cbt/CBT1000001"}

    async def fake_token(**kwargs):
        assert kwargs["store"].seller_id == "2942677449"
        return "access-token"

    monkeypatch.setattr(publishing.settings, "allow_live_publish", True)
    monkeypatch.setattr(publishing.settings, "token_encryption_key", "test-secret")
    monkeypatch.setattr(publishing, "MercadoLibreClient", FakeClient)
    monkeypatch.setattr(publishing, "resolve_fresh_store_access_token", fake_token)
    client = make_client()

    first = client.post(
        "/api/publishing/cbt/execute-from-draft",
        json={"product_draft_id": 1, "acknowledge_publish": True},
    )
    replay = client.post(
        "/api/publishing/cbt/execute-from-draft",
        json={"product_draft_id": 1, "acknowledge_publish": True},
    )

    assert first.status_code == 200
    assert first.json()["status"] == "published"
    assert first.json()["item_id"] == "CBT1000001"
    assert replay.status_code == 200
    assert replay.json()["item_id"] == "CBT1000001"
    assert len(calls) == 1
    assert calls[0][0] == "/global/items"
    assert calls[0][1]["sites_to_sell"][0]["pictures"] == [
        {"source": "https://example.com/source.jpg"}
    ]


def test_cbt_execute_blocks_stale_config_before_token_resolution(monkeypatch):
    async def unexpected_token(**kwargs):
        raise AssertionError("A stale CBT config must not resolve a token.")

    monkeypatch.setattr(publishing.settings, "allow_live_publish", True)
    monkeypatch.setattr(publishing, "resolve_fresh_store_access_token", unexpected_token)
    client = make_client()
    generator = app.dependency_overrides[get_db]()
    db = next(generator)
    try:
        config = db.query(CbtListingConfig).one()
        config.draft_content_version = 1
        db.commit()
    finally:
        generator.close()

    response = client.post(
        "/api/publishing/cbt/execute-from-draft",
        json={"product_draft_id": 1, "acknowledge_publish": True},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "blocked"
    assert response.json()["errors"] == ["cbt_listing_config_stale_save_again_required"]
