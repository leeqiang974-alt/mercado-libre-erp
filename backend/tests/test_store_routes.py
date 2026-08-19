import httpx
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import stores
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.registry import import_all_models
from app.models.store import Store
from app.services.meli.client import MercadoLibreClient
from app.services.meli.oauth import MercadoLibreOAuthClient, create_state_token


def make_client(with_session: bool = False):
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
    client = TestClient(app)
    return (client, testing_session) if with_session else client


def teardown_function():
    app.dependency_overrides.clear()


def test_authorization_url_route_returns_url(monkeypatch):
    monkeypatch.setattr(stores.settings, "meli_client_id", "client-123")
    monkeypatch.setattr(stores.settings, "meli_client_secret", "secret-456")
    monkeypatch.setattr(
        stores.settings,
        "meli_redirect_uri",
        "http://localhost:8000/api/stores/meli/callback",
    )
    client = make_client()

    response = client.get("/api/stores/meli/authorization-url")

    assert response.status_code == 200
    body = response.json()
    assert body["authorization_url"].startswith("https://auth.mercadolibre.com.mx/authorization?")
    assert body["site_id"] == "MLM"
    assert "state=" in body["authorization_url"]


def test_authorization_url_rejects_unsupported_site(monkeypatch):
    monkeypatch.setattr(stores.settings, "meli_client_id", "client-123")
    monkeypatch.setattr(stores.settings, "meli_client_secret", "secret-456")
    client = make_client()

    response = client.get("/api/stores/meli/authorization-url?site_id=UNKNOWN")

    assert response.status_code == 422
    assert response.json()["detail"] == "Unsupported Mercado Libre site."


def test_callback_rejects_invalid_oauth_state(monkeypatch):
    monkeypatch.setattr(stores.settings, "token_encryption_key", "test-secret")
    monkeypatch.setattr(
        stores,
        "create_oauth_client",
        lambda: (_ for _ in ()).throw(AssertionError("OAuth exchange must not run")),
    )
    client = make_client()

    response = client.get("/api/stores/meli/callback?code=code-789&state=forged-state")

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid or expired OAuth state."


def test_callback_exchanges_code_without_returning_tokens(monkeypatch):
    monkeypatch.setattr(stores.settings, "meli_client_id", "client-123")
    monkeypatch.setattr(stores.settings, "meli_client_secret", "secret-456")
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/users/me":
            return httpx.Response(200, json={"id": 123, "site_id": "MLM", "nickname": "seller"})
        return httpx.Response(
            200,
            json={
                "access_token": "access-token",
                "refresh_token": "refresh-token",
                "expires_in": 21600,
                "user_id": 123,
            },
        )

    def fake_client(db=None) -> MercadoLibreOAuthClient:
        return MercadoLibreOAuthClient(
            client_id="client-123",
            client_secret="secret-456",
            redirect_uri="http://localhost:8000/api/stores/meli/callback",
            transport=httpx.MockTransport(handler),
        )

    monkeypatch.setattr(stores, "create_oauth_client", fake_client)
    monkeypatch.setattr(
        stores,
        "create_meli_client",
        lambda access_token: MercadoLibreClient(
            access_token=access_token,
            transport=httpx.MockTransport(handler),
        ),
    )
    client = make_client()

    state = create_state_token(stores.settings.token_encryption_key, "MLM")
    response = client.get(
        f"/api/stores/meli/callback?code=code-789&state={state}",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].endswith(
        "?meli_auth=authorized&seller_id=123&site_id=MLM"
    )
    assert "access-token" not in response.text
    assert "refresh-token" not in response.text

    stores_response = client.get("/api/stores")
    assert stores_response.json()[0]["site_id"] == "MLM"
    assert "token_reference" not in stores_response.json()[0]


def test_callback_rejects_seller_from_different_requested_site(monkeypatch):
    monkeypatch.setattr(stores.settings, "meli_client_id", "client-123")
    monkeypatch.setattr(stores.settings, "meli_client_secret", "secret-456")

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/users/me":
            return httpx.Response(200, json={"id": 123, "site_id": "MLA"})
        return httpx.Response(
            200,
            json={
                "access_token": "access-token",
                "refresh_token": "refresh-token",
                "expires_in": 21600,
                "user_id": 123,
            },
        )

    monkeypatch.setattr(
        stores,
        "create_oauth_client",
        lambda db=None: MercadoLibreOAuthClient(
            client_id="client-123",
            client_secret="secret-456",
            redirect_uri="http://localhost:8000/api/stores/meli/callback",
            transport=httpx.MockTransport(handler),
        ),
    )
    monkeypatch.setattr(
        stores,
        "create_meli_client",
        lambda access_token: MercadoLibreClient(
            access_token=access_token,
            transport=httpx.MockTransport(handler),
        ),
    )
    client = make_client()
    state = create_state_token(stores.settings.token_encryption_key, "MLM")

    response = client.get(
        f"/api/stores/meli/callback?code=code-789&state={state}",
        follow_redirects=False,
    )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "Authorized seller site does not match the requested site."
    )
    assert client.get("/api/stores").json() == []


def test_store_shipping_options_exclude_full(monkeypatch):
    monkeypatch.setattr(stores.settings, "meli_client_id", "client-123")
    monkeypatch.setattr(stores.settings, "meli_client_secret", "secret-456")
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/users/me":
            return httpx.Response(200, json={"id": 123, "site_id": "MLM"})
        if request.url.path == "/users/123/shipping_preferences":
            return httpx.Response(
                200,
                json={
                    "modes": ["me2", "me1"],
                    "logistics": [
                        {"mode": "me2", "types": ["fulfillment", "drop_off"]}
                    ],
                },
            )
        return httpx.Response(
            200,
            json={
                "access_token": "access-token",
                "refresh_token": "refresh-token",
                "expires_in": 21600,
                "user_id": 123,
            },
        )

    monkeypatch.setattr(
        stores,
        "create_oauth_client",
        lambda db=None: MercadoLibreOAuthClient(
            client_id="client-123",
            client_secret="secret-456",
            redirect_uri="http://localhost:8000/api/stores/meli/callback",
            transport=httpx.MockTransport(handler),
        ),
    )
    monkeypatch.setattr(
        stores,
        "create_meli_client",
        lambda access_token: MercadoLibreClient(
            access_token=access_token,
            transport=httpx.MockTransport(handler),
        ),
    )
    client = make_client()
    state = create_state_token(stores.settings.token_encryption_key, "MLM")
    client.get(
        f"/api/stores/meli/callback?code=code-789&state={state}",
        follow_redirects=False,
    )

    response = client.get("/api/stores/1/shipping-options")

    assert response.status_code == 200
    assert response.json() == {
        "store_id": 1,
        "site_id": "MLM",
        "verified": True,
        "options": [
            {"mode": "me2", "logistic_type": "drop_off"},
            {"mode": "me1", "logistic_type": "default"},
        ],
    }


def test_store_category_listing_types_use_authorized_seller_eligibility(monkeypatch):
    monkeypatch.setattr(stores.settings, "meli_client_id", "client-123")
    monkeypatch.setattr(stores.settings, "meli_client_secret", "secret-456")

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/users/me":
            return httpx.Response(200, json={"id": 123, "site_id": "MLM"})
        if request.url.path == "/users/123/available_listing_types":
            assert request.url.params["category_id"] == "MLM123"
            return httpx.Response(
                200,
                json={
                    "category_id": "MLM123",
                    "available": [
                        {
                            "site_id": "MLM",
                            "id": "gold_special",
                            "name": "Clásica",
                            "remaining_listings": None,
                        },
                        {"site_id": "MLM", "id": "free", "name": "Gratuita"},
                    ],
                },
            )
        return httpx.Response(
            200,
            json={
                "access_token": "access-token",
                "refresh_token": "refresh-token",
                "expires_in": 21600,
                "user_id": 123,
            },
        )

    monkeypatch.setattr(
        stores,
        "create_oauth_client",
        lambda db=None: MercadoLibreOAuthClient(
            client_id="client-123",
            client_secret="secret-456",
            redirect_uri="http://localhost:8000/api/stores/meli/callback",
            transport=httpx.MockTransport(handler),
        ),
    )
    monkeypatch.setattr(
        stores,
        "create_meli_client",
        lambda access_token: MercadoLibreClient(
            access_token=access_token,
            transport=httpx.MockTransport(handler),
        ),
    )
    client = make_client()
    state = create_state_token(stores.settings.token_encryption_key, "MLM")
    client.get(
        f"/api/stores/meli/callback?code=code-789&state={state}",
        follow_redirects=False,
    )

    response = client.get("/api/stores/1/categories/MLM123/listing-types")

    assert response.status_code == 200
    assert response.json()["listing_types"] == [
        {
            "id": "gold_special",
            "name": "Clásica",
            "site_id": "MLM",
            "remaining_listings": None,
        }
    ]


def test_store_category_listing_types_reject_cross_site_category(monkeypatch):
    client, testing_session = make_client(with_session=True)
    with testing_session() as db:
        db.add(
            Store(
                site_id="MLM",
                seller_id="123",
                display_name="Demo",
                oauth_status="connected",
            )
        )
        db.commit()

    response = client.get("/api/stores/1/categories/MLA123/listing-types")

    assert response.status_code == 422
    assert response.json()["detail"] == "Category site does not match store site."


def test_cbt_item_price_reference_returns_official_cost_fields(monkeypatch):
    client, testing_session = make_client(with_session=True)
    with testing_session() as db:
        db.add(Store(site_id="CBT", seller_id="2942677449", display_name="Global", oauth_status="connected"))
        db.commit()

    async def fresh_token(**kwargs):
        return "access-token"

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/marketplace/benchmarks/items/CBT123/details"
        return httpx.Response(200, json={
            "item_id": "CBT123", "status": "with_benchmark_high", "currency_id": "USD",
            "current_price": {"amount": 100, "usd_amount": 100},
            "suggested_price": {"amount": 90, "usd_amount": 90},
            "estimated_taxes": {"amount": 12, "usd_amount": 12},
            "costs": {"selling_fees": 15, "shipping_fees": 8},
            "percent_difference": 11.11, "applicable_suggestion": True,
            "last_updated": "09-12-2025 14:33:36",
        })

    monkeypatch.setattr(stores, "resolve_fresh_store_access_token", fresh_token)
    monkeypatch.setattr(stores, "create_meli_client", lambda token: MercadoLibreClient(token, transport=httpx.MockTransport(handler)))

    response = client.get("/api/stores/1/items/CBT123/price-reference")

    assert response.status_code == 200
    assert response.json()["availability"] == "available"
    assert response.json()["estimated_after_reference_costs"] == 65.0
    assert response.json()["selling_fees"] == 15


def test_cbt_item_price_reference_treats_documented_404_as_unavailable(monkeypatch):
    client, testing_session = make_client(with_session=True)
    with testing_session() as db:
        db.add(Store(site_id="CBT", seller_id="2942677449", display_name="Global", oauth_status="connected"))
        db.commit()

    async def fresh_token(**kwargs):
        return "access-token"

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"message": "Item price reference not found"})

    monkeypatch.setattr(stores, "resolve_fresh_store_access_token", fresh_token)
    monkeypatch.setattr(stores, "create_meli_client", lambda token: MercadoLibreClient(token, transport=httpx.MockTransport(handler)))

    response = client.get("/api/stores/1/items/CBT123/price-reference")

    assert response.status_code == 200
    assert response.json()["availability"] == "unavailable"
    assert response.json()["reason"] == "official_no_reference"


def test_cbt_parent_price_reference_requires_a_marketplace_child_item(monkeypatch):
    client, testing_session = make_client(with_session=True)
    with testing_session() as db:
        db.add(Store(site_id="CBT", seller_id="2942677449", display_name="Global", oauth_status="connected"))
        db.commit()

    async def fresh_token(**kwargs):
        return "access-token"

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"message": "Invalid site id for item"})

    monkeypatch.setattr(stores, "resolve_fresh_store_access_token", fresh_token)
    monkeypatch.setattr(stores, "create_meli_client", lambda token: MercadoLibreClient(token, transport=httpx.MockTransport(handler)))

    response = client.get("/api/stores/1/items/CBT123/price-reference")

    assert response.status_code == 200
    assert response.json()["availability"] == "unavailable"
    assert response.json()["reason"] == "requires_marketplace_child_item"
