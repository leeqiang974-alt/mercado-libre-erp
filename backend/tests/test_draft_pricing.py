from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.audit_event import AuditEvent
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


def test_pricing_is_calculated_saved_and_audited():
    client, testing_session = make_client()
    payload = {
        "source_price": 10,
        "source_currency": "usd",
        "target_currency": "mxn",
        "exchange_rate": 18,
        "purchase_extra_cost": 20,
        "shipping_cost": 50,
        "platform_fee_rate": 0.15,
        "tax_rate": 0.05,
        "profit_margin_rate": 0.2,
        "rounding_increment": 10,
    }

    response = client.put("/api/drafts/1/pricing", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["source_currency"] == "USD"
    assert body["target_currency"] == "MXN"
    assert body["landed_cost"] == 250
    assert body["target_price"] == 420

    saved = client.get("/api/drafts/1/pricing")
    assert saved.status_code == 200
    assert saved.json()["target_price"] == 420

    with testing_session() as db:
        draft = db.get(ProductDraft, 1)
        assert draft.price == 420
        assert draft.currency == "MXN"
        event = db.query(AuditEvent).one()
        assert event.action == "draft_pricing_updated"
        assert event.after_json["price"] == 420


def test_existing_pricing_config_update_persists_new_calculation():
    client, _ = make_client()
    payload = {
        "source_price": 10,
        "source_currency": "USD",
        "target_currency": "MXN",
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


def test_pricing_rejects_impossible_rate_total():
    client, _ = make_client()

    response = client.put(
        "/api/drafts/1/pricing",
        json={
            "source_price": 10,
            "source_currency": "USD",
            "target_currency": "MXN",
            "exchange_rate": 18,
            "platform_fee_rate": 0.5,
            "tax_rate": 0.2,
            "profit_margin_rate": 0.3,
        },
    )

    assert response.status_code == 422
    assert "must total less than 100%" in response.text


def test_missing_pricing_can_be_read_as_optional():
    client, _ = make_client()

    response = client.get("/api/drafts/1/pricing?optional=true")

    assert response.status_code == 200
    assert response.json() is None
