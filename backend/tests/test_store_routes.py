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
from app.services.meli.client import MercadoLibreClient
from app.services.meli.oauth import MercadoLibreOAuthClient, create_state_token


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


def test_authorization_url_route_returns_url(monkeypatch):
    monkeypatch.setattr(stores.settings, "meli_client_id", "client-123")
    monkeypatch.setattr(
        stores.settings,
        "meli_redirect_uri",
        "http://localhost:8000/api/stores/meli/callback",
    )
    client = make_client()

    response = client.get("/api/stores/meli/authorization-url")

    assert response.status_code == 200
    body = response.json()
    assert body["authorization_url"].startswith("https://auth.mercadolibre.com/authorization?")
    assert "state=" in body["authorization_url"]


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

    def fake_client() -> MercadoLibreOAuthClient:
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

    state = create_state_token(stores.settings.token_encryption_key)
    response = client.get(
        f"/api/stores/meli/callback?code=code-789&state={state}",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].endswith("?meli_auth=authorized&seller_id=123")
    assert "access-token" not in response.text
    assert "refresh-token" not in response.text

    stores_response = client.get("/api/stores")
    assert stores_response.json()[0]["site_id"] == "MLM"
    assert "token_reference" not in stores_response.json()[0]


def test_store_shipping_options_exclude_full(monkeypatch):
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
        lambda: MercadoLibreOAuthClient(
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
    state = create_state_token(stores.settings.token_encryption_key)
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
