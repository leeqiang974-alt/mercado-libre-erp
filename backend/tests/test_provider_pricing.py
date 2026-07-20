from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.audit_event import AuditEvent
from app.models.draft_listing_config import DraftListingConfig
from app.models.meli_metadata_cache import MeliMetadataCache
from app.models.product_draft import ProductDraft
from app.models.provider_model_price import ProviderModelPrice
from app.models.registry import import_all_models
from app.models.review_result import ReviewResult
from app.models.store import Store
from app.schemas.provider_pricing import ProviderModelPriceCreate
from app.schemas.reviews import ReviewResponse
from app.services.provider_pricing import save_provider_model_price
from app.services.reviews import persist_review_result
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

    def override_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    return TestClient(app), testing_session


def teardown_function():
    app.dependency_overrides.clear()


def _price_payload(input_price: str, output_price: str) -> dict:
    return {
        "provider": "claude",
        "model": "claude-test-model",
        "currency": "USD",
        "input_price_per_million": input_price,
        "output_price_per_million": output_price,
    }


def test_model_price_api_appends_versions_and_can_deactivate_current_price():
    client, testing_session = make_client()

    first = client.put("/api/integrations/model-prices", json=_price_payload("3", "15"))
    second = client.put("/api/integrations/model-prices", json=_price_payload("4", "16"))

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["version"] == 1
    assert second.json()["version"] == 2
    current = client.get("/api/integrations/model-prices").json()
    history = client.get("/api/integrations/model-prices?include_history=true").json()
    assert [(row["version"], row["active"]) for row in current] == [(2, True)]
    assert [(row["version"], row["active"]) for row in history] == [
        (2, True),
        (1, False),
    ]

    removed = client.delete(f"/api/integrations/model-prices/{second.json()['id']}")

    assert removed.status_code == 200
    assert removed.json()["active"] is False
    assert client.get("/api/integrations/model-prices").json() == []
    with testing_session() as db:
        assert db.query(ProviderModelPrice).count() == 2
        assert db.query(AuditEvent).count() == 3


def test_model_price_api_rejects_non_ascii_currency_before_database_write():
    client, testing_session = make_client()
    payload = _price_payload("3", "15") | {"currency": "ßßß"}

    response = client.put("/api/integrations/model-prices", json=payload)

    assert response.status_code == 422
    with testing_session() as db:
        assert db.query(ProviderModelPrice).count() == 0


def test_persisted_review_cost_keeps_the_exact_price_version_snapshot():
    _, testing_session = make_client()
    with testing_session() as db:
        db.add(MeliMetadataCache(
            cache_key="category_attributes:MLM123",
            payload_json={"attributes": [{"id": "ITEM_CONDITION", "value_type": "list", "values": [{"id": "2230284", "name": "New"}], "tags": {"hidden": True}}], "verified": True},
        ))
        draft = ProductDraft(
            title="Bottle",
            description="Leak proof.",
            target_site_id="MLM",
            target_category_id="MLM123",
            source_price=10,
            source_currency="USD",
            price=300,
            currency="MXN",
            stock=1,
            image_urls_json=["https://example.com/a.jpg"],
        )
        db.add(draft)
        db.flush()
        add_current_pricing(db, draft)
        db.add(Store(
            id=1,
            site_id="MLM",
            seller_id="seller-1",
            display_name="Test Store",
            oauth_status="connected",
        ))
        db.add(DraftListingConfig(
            product_draft_id=draft.id,
            store_id=1,
            site_id="MLM",
            category_id="MLM123",
            listing_type_id="gold_special",
            fulfillment="not_full",
            shipping_mode="me2",
            shipping_logistic_type="drop_off",
            available_quantity=1,
            attributes_json=[{"id": "ITEM_CONDITION", "value_id": "2230284", "value_name": "New"}],
        ))
        first_price = save_provider_model_price(
            db,
            ProviderModelPriceCreate(
                provider="claude",
                model="claude-test-model",
                currency="USD",
                input_price_per_million=Decimal("3"),
                output_price_per_million=Decimal("15"),
            ),
        )
        result = persist_review_result(
            db,
            draft.id,
            ReviewResponse(
                provider="claude",
                decision="pass",
                risk_level="low",
                reason_codes=[],
                reasons=["ok"],
                input_tokens=1000,
                output_tokens=500,
                total_tokens=1500,
            ),
            model="claude-test-model",
        )
        assert result.price_config_id == first_price.id
        assert result.estimated_cost_amount == Decimal("0.01050000")
        save_provider_model_price(
            db,
            ProviderModelPriceCreate(
                provider="claude",
                model="claude-test-model",
                currency="USD",
                input_price_per_million=Decimal("30"),
                output_price_per_million=Decimal("150"),
            ),
        )
        db.expire_all()
        historical = db.get(ReviewResult, result.id)
        assert historical is not None
        assert historical.price_config_id == first_price.id
        assert historical.estimated_cost_amount == Decimal("0.01050000")
        assert historical.estimated_cost_currency == "USD"


def test_review_cost_is_unknown_without_tokens_or_an_active_price():
    _, testing_session = make_client()
    with testing_session() as db:
        save_provider_model_price(
            db,
            ProviderModelPriceCreate(
                provider="nvidia",
                model="nvidia-test-model",
                currency="USD",
                input_price_per_million=Decimal("1"),
                output_price_per_million=Decimal("2"),
            ),
        )
        from app.services.provider_pricing import estimate_review_cost

        missing_tokens = estimate_review_cost(
            db,
            provider="nvidia",
            model="nvidia-test-model",
            input_tokens=None,
            output_tokens=10,
        )
        missing_price = estimate_review_cost(
            db,
            provider="claude",
            model="unpriced-model",
            input_tokens=10,
            output_tokens=10,
        )
        assert missing_tokens.amount is None
        assert missing_tokens.price_config_id is not None
        assert missing_tokens.currency == "USD"
        assert missing_price.amount is None


def test_review_cost_uses_price_captured_when_the_request_started():
    _, testing_session = make_client()
    with testing_session() as db:
        first = save_provider_model_price(
            db,
            ProviderModelPriceCreate(
                provider="claude",
                model="claude-test-model",
                currency="USD",
                input_price_per_million=Decimal("3"),
                output_price_per_million=Decimal("15"),
            ),
        )
        from app.services.provider_pricing import estimate_review_cost

        captured_id = first.id
        save_provider_model_price(
            db,
            ProviderModelPriceCreate(
                provider="claude",
                model="claude-test-model",
                currency="USD",
                input_price_per_million=Decimal("30"),
                output_price_per_million=Decimal("150"),
            ),
        )
        estimate = estimate_review_cost(
            db,
            provider="claude",
            model="claude-test-model",
            input_tokens=1000,
            output_tokens=500,
            price_config_id=captured_id,
            price_config_captured=True,
        )
        assert estimate.price_config_id == captured_id
        assert estimate.amount == Decimal("0.01050000")

        missing_at_start = estimate_review_cost(
            db,
            provider="nvidia",
            model="nvidia-test-model",
            input_tokens=1000,
            output_tokens=500,
            price_config_id=None,
            price_config_captured=True,
        )
        assert missing_at_start.amount is None


def test_cost_calculation_supports_maximum_valid_rates_and_integer_token_counts():
    _, testing_session = make_client()
    with testing_session() as db:
        price = save_provider_model_price(
            db,
            ProviderModelPriceCreate(
                provider="claude",
                model="maximum-cost-model",
                currency="USD",
                input_price_per_million=Decimal("999999999999.999999"),
                output_price_per_million=Decimal("999999999999.999999"),
            ),
        )
        from app.services.provider_pricing import estimate_review_cost

        estimate = estimate_review_cost(
            db,
            provider="claude",
            model="maximum-cost-model",
            input_tokens=2_147_483_647,
            output_tokens=2_147_483_647,
            price_config_id=price.id,
            price_config_captured=True,
        )
        assert estimate.amount is not None
        assert estimate.amount > Decimal("1000000000000000")
        assert estimate.amount.as_tuple().exponent == -8
