import httpx
from fastapi.testclient import TestClient

from app.api.routes import stores
from app.main import app
from app.services.meli.oauth import MercadoLibreOAuthClient


def test_authorization_url_route_returns_url(monkeypatch):
    monkeypatch.setattr(stores.settings, "meli_client_id", "client-123")
    monkeypatch.setattr(
        stores.settings,
        "meli_redirect_uri",
        "http://localhost:8000/api/stores/meli/callback",
    )
    client = TestClient(app)

    response = client.get("/api/stores/meli/authorization-url")

    assert response.status_code == 200
    body = response.json()
    assert body["authorization_url"].startswith("https://auth.mercadolibre.com/authorization?")
    assert body["state"]


def test_callback_exchanges_code_without_returning_tokens(monkeypatch):
    async def handler(request: httpx.Request) -> httpx.Response:
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
    client = TestClient(app)

    response = client.get("/api/stores/meli/callback?code=code-789&state=state-abc")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "authorized"
    assert body["seller_id"] == "123"
    assert "access-token" not in response.text
    assert "refresh-token" not in response.text
