from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.registry import import_all_models


def make_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    import_all_models()
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)

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


def test_import_review_publish_preview_flow():
    client = make_client()
    imported = client.post(
        "/api/imports/amazon-html",
        json={
            "source_url": "https://www.amazon.com/dp/B000TEST",
            "html": "<span id='productTitle'>Bottle</span><span class='a-price'><span class='a-offscreen'>$9.99</span></span><img id='landingImage' src='https://example.com/a.jpg' />",
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
            "exchange_rate": 18,
            "shipping_cost": 40,
            "platform_fee_rate": 0.15,
            "profit_margin_rate": 0.2,
            "rounding_increment": 10,
        },
    )
    assert priced.status_code == 200
    draft = client.get("/api/drafts").json()[0]
    draft["target_category_id"] = "MLM123"

    reviewed = client.post(f"/api/reviews/local?product_draft_id={draft_id}", json=draft)
    assert reviewed.status_code == 200
    assert reviewed.json()["decision"] == "pass"

    preview = client.post(
        "/api/publishing/preview",
        json={
            "draft": draft,
            "review": reviewed.json(),
            "listing_choice": {
                "site_id": "MLM",
                "listing_type_id": "gold_special",
                "fulfillment": "not_full",
            },
            "valid_listing_type_ids": ["gold_special", "gold_pro"],
            "human_approved": True,
        },
    )
    assert preview.status_code == 200
    assert preview.json()["allowed"] is True
