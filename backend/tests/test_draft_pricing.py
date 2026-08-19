from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.audit_event import AuditEvent
from app.models.draft_pricing_config import DraftPricingConfig
from app.models.product_draft import ProductDraft
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
    with testing_session() as db:
        db.add(
            ProductDraft(
                title="Amazon product",
                description="Source product",
                target_site_id="MLM",
                source_price=10,
                source_currency="USD",
                price=None,
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
    return TestClient(app), testing_session


def teardown_function():
    app.dependency_overrides.clear()


def review_draft_payload():
    return {
        "title": "Amazon product",
        "description": "Source product",
        "target_site_id": "MLM",
        "source_price": 10,
        "source_currency": "USD",
        "price": 420,
        "currency": "MXN",
        "stock": 2,
        "image_urls": ["https://example.com/a.jpg"],
    }


def test_pricing_is_calculated_saved_and_audited():
    client, testing_session = make_client()
    payload = {
        "source_price": 10,
        "source_currency": "usd",
        "target_currency": "mxn",
        "cost_currency": "cny",
        "purchase_cost": 100,
        "domestic_shipping_cost": 20,
        "exchange_rate": 2,
        "profit_margin_rate": 0.25,
        "rounding_increment": 1,
    }

    response = client.put("/api/drafts/1/pricing", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["source_currency"] == "USD"
    assert body["target_currency"] == "MXN"
    assert body["cost_currency"] == "CNY"
    assert body["purchase_cost"] == 100
    assert body["domestic_shipping_cost"] == 20
    assert body["landed_cost"] == 240
    assert body["target_price"] == 300
    assert body["draft_content_version"] == 2
    assert body["draft"]["content_version"] == 2
    assert body["draft"]["price"] == 300

    saved = client.get("/api/drafts/1/pricing")
    assert saved.status_code == 200
    assert saved.json()["target_price"] == 300
    assert saved.json()["draft_content_version"] == 2
    assert saved.json()["draft"]["content_version"] == 2

    with testing_session() as db:
        draft = db.get(ProductDraft, 1)
        assert draft.price == 300
        assert draft.currency == "MXN"
        event = db.query(AuditEvent).one()
        assert event.action == "draft_pricing_updated"
        assert event.after_json["price"] == 300


def test_existing_pricing_config_update_persists_new_calculation():
    client, _ = make_client()
    payload = {
        "source_price": 10,
        "source_currency": "USD",
        "target_currency": "MXN",
        "cost_currency": "CNY",
        "purchase_cost": 100,
        "domestic_shipping_cost": 10,
        "exchange_rate": 18,
        "rounding_increment": 10,
    }
    client.put("/api/drafts/1/pricing", json=payload)

    response = client.put(
        "/api/drafts/1/pricing",
        json=payload | {"exchange_rate": 20},
    )

    assert response.status_code == 200
    assert response.json()["exchange_rate"] == 20
    assert client.get("/api/drafts/1/pricing").json()["exchange_rate"] == 20


def test_pricing_rejects_marketplace_cost_inputs():
    client, _ = make_client()

    response = client.put(
        "/api/drafts/1/pricing",
        json={
            "source_price": 10,
            "source_currency": "USD",
            "target_currency": "MXN",
            "cost_currency": "CNY",
            "purchase_cost": 100,
            "domestic_shipping_cost": 10,
            "exchange_rate": 18,
            "platform_fee_rate": 0.5,
        },
    )

    assert response.status_code == 422
    assert "not per-item Global Selling price inputs" in response.text


def test_missing_pricing_can_be_read_as_optional():
    client, _ = make_client()

    response = client.get("/api/drafts/1/pricing?optional=true")

    assert response.status_code == 200
    assert response.json() is None


def test_pricing_rejects_source_evidence_and_site_currency_changes():
    client, testing_session = make_client()
    base = {
        "source_price": 10,
        "source_currency": "USD",
        "target_currency": "MXN",
        "cost_currency": "CNY",
        "purchase_cost": 100,
        "domestic_shipping_cost": 10,
        "exchange_rate": 18,
    }

    changed_price = client.put(
        "/api/drafts/1/pricing",
        json=base | {"source_price": 11},
    )
    changed_currency = client.put(
        "/api/drafts/1/pricing",
        json=base | {"source_currency": "EUR"},
    )
    wrong_target = client.put(
        "/api/drafts/1/pricing",
        json=base | {"target_currency": "USD"},
    )
    near_price = client.put(
        "/api/drafts/1/pricing",
        json=base | {"source_price": 10.0000000005},
    )

    assert changed_price.status_code == 422
    assert "source_price_is_read_only" in changed_price.json()["detail"]["errors"]
    assert changed_currency.status_code == 422
    assert "source_currency_is_read_only" in changed_currency.json()["detail"]["errors"]
    assert wrong_target.status_code == 422
    assert "target_currency_mismatch" in wrong_target.json()["detail"]["errors"]
    assert near_price.status_code == 422
    assert "source_price_is_read_only" in near_price.json()["detail"]["errors"]
    with testing_session() as db:
        draft = db.get(ProductDraft, 1)
        assert draft.source_price == 10
        assert draft.source_currency == "USD"
        assert draft.price is None


def test_persisted_review_requires_saved_pricing():
    client, _ = make_client()

    response = client.post(
        "/api/reviews/local?product_draft_id=1",
        json=review_draft_payload(),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == {
        "code": "draft_pricing_not_ready",
        "errors": ["saved_pricing_required"],
    }


def test_persisted_review_rejects_price_tampered_after_pricing_save():
    client, testing_session = make_client()
    pricing = {
        "source_price": 10,
        "source_currency": "USD",
        "target_currency": "MXN",
        "cost_currency": "CNY",
        "purchase_cost": 100,
        "domestic_shipping_cost": 20,
        "exchange_rate": 2,
        "profit_margin_rate": 0.2,
        "rounding_increment": 1,
    }
    assert client.put("/api/drafts/1/pricing", json=pricing).status_code == 200
    with testing_session() as db:
        draft = db.get(ProductDraft, 1)
        draft.price = 421
        db.commit()

    response = client.post(
        "/api/reviews/local?product_draft_id=1",
        json=review_draft_payload(),
    )
    pricing_response = client.get("/api/drafts/1/pricing?optional=true")

    assert response.status_code == 409
    assert "draft_price_not_from_saved_pricing" in response.json()["detail"]["errors"]
    assert pricing_response.status_code == 409
    assert "draft_price_not_from_saved_pricing" in pricing_response.text


def test_persisted_review_rejects_saved_source_price_drift():
    client, testing_session = make_client()
    pricing = {
        "source_price": 10,
        "source_currency": "USD",
        "target_currency": "MXN",
        "cost_currency": "CNY",
        "purchase_cost": 100,
        "domestic_shipping_cost": 10,
        "exchange_rate": 18,
        "rounding_increment": 1,
    }
    assert client.put("/api/drafts/1/pricing", json=pricing).status_code == 200
    with testing_session() as db:
        config = db.query(DraftPricingConfig).one()
        config.source_price = 10.0000000005
        db.commit()

    response = client.post(
        "/api/reviews/local?product_draft_id=1",
        json=review_draft_payload(),
    )

    assert response.status_code == 409
    assert "pricing_source_price_mismatch" in response.json()["detail"]["errors"]
