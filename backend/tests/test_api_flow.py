from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import publishing
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.registry import import_all_models
from app.models.meli_metadata_cache import MeliMetadataCache
from app.models.store import Store


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
                seller_id="api-flow",
                display_name="API Flow Store",
                oauth_status="connected",
            )
        db.add(store)
        db.flush()
        db.add(
            MeliMetadataCache(
                cache_key=f"available_listing_types:{store.id}:MLM123",
                payload_json={
                    "verified": True,
                    "store_id": store.id,
                    "category_id": "MLM123",
                    "listing_types": [{"id": "gold_special"}, {"id": "gold_pro"}],
                },
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


def test_import_review_publish_preview_flow(monkeypatch):
    def current_shipping(*args, **kwargs):
        return []

    monkeypatch.setattr(publishing, "_validate_current_store_shipping", current_shipping)
    client = make_client()
    imported = client.post(
        "/api/imports/amazon-html",
        json={
            "source_url": "https://www.amazon.com/dp/B000TEST01",
            "html": "<input id='ASIN' value='B000TEST01' /><span id='productTitle'>Bottle</span><span class='a-price'><span class='a-offscreen'>$9.99</span></span><div id='productDescription'>Leak proof bottle.</div><img id='landingImage' src='https://example.com/a.jpg' />",
            "target_site_id": "MLM",
            "persist": True,
        },
    )
    assert imported.status_code == 200
    draft_id = imported.json()["id"]
    draft = imported.json()["draft"]
    assert draft["title"] == "Bottle"
    assert draft["source_price"] == 9.99
    assert draft["price"] is None

    priced = client.put(
        f"/api/drafts/{draft_id}/pricing",
        json={
            "source_price": draft["source_price"],
            "source_currency": draft["source_currency"],
            "target_currency": "MXN",
            "cost_currency": "CNY",
            "purchase_cost": 100,
            "domestic_shipping_cost": 10,
            "exchange_rate": 18,
            "profit_margin_rate": 0.2,
            "rounding_increment": 1,
        },
    )
    assert priced.status_code == 200
    draft = client.get("/api/drafts").json()[0]
    draft["target_category_id"] = "MLM123"
    draft["stock"] = 1
    draft["condition"] = "new"

    reviewed = client.post("/api/reviews/local", json=draft)
    assert reviewed.status_code == 200
    assert reviewed.json()["decision"] == "pass"

    preview = client.post(
        "/api/publishing/preview",
        json={
            "draft": draft,
            "review": reviewed.json(),
                "listing_choice": {
                    "site_id": "MLM",
                    "store_id": 1,
                    "listing_type_id": "gold_special",
                    "fulfillment": "not_full",
                    "shipping_mode": "me2",
                    "shipping_logistic_type": "drop_off",
                    "attributes": [
                        {"id": "ITEM_CONDITION", "value_id": "2230284", "value_name": "New"},
                    ],
                },
            "valid_listing_type_ids": ["gold_special", "gold_pro"],
            "human_approved": True,
        },
    )
    assert preview.status_code == 200
    assert preview.json()["allowed"] is True
