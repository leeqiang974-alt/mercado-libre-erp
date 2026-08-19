import httpx
import pytest

from app.services.meli.oauth import (
    MercadoLibreOAuthClient,
    build_authorization_url,
    create_state_token,
    get_state_site_id,
    verify_state_token,
)
from app.services.meli.sites import SITE_CURRENCIES, SITE_MARKETPLACE_DOMAINS


def test_build_authorization_url_contains_required_params():
    url = build_authorization_url(
        client_id="client-123",
        redirect_uri="http://localhost:8000/api/stores/meli/callback",
        state="state-abc",
        site_id="MLM",
    )

    assert url.startswith("https://auth.mercadolibre.com.mx/authorization?")
    assert "response_type=code" in url
    assert "client_id=client-123" in url
    assert "redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Fapi%2Fstores%2Fmeli%2Fcallback" in url
    assert "state=state-abc" in url


def test_create_state_token_is_url_safe_and_non_empty():
    state = create_state_token("test-secret", "MLM")
    assert len(state) >= 24
    assert "+" not in state
    assert "/" not in state


def test_state_token_rejects_tampering_and_accepts_matching_secret():
    state = create_state_token("test-secret", "MLB")

    assert verify_state_token(state, "test-secret") is True
    assert get_state_site_id(state, "test-secret") == "MLB"
    assert verify_state_token(f"{state}tampered", "test-secret") is False
    assert verify_state_token(state, "other-secret") is False


@pytest.mark.parametrize(
    ("site_id", "expected_prefix"),
    [
        ("MLA", "https://auth.mercadolibre.com.ar/authorization?"),
        ("MLB", "https://auth.mercadolivre.com.br/authorization?"),
        ("MLU", "https://auth.mercadolibre.com.uy/authorization?"),
    ],
)
def test_authorization_url_uses_site_marketplace_domain(site_id, expected_prefix):
    state = create_state_token("test-secret", site_id)

    url = build_authorization_url("client-123", "https://example.com/callback", state, site_id)

    assert url.startswith(expected_prefix)


def test_every_supported_marketplace_site_has_an_authorization_domain():
    assert set(SITE_MARKETPLACE_DOMAINS) == set(SITE_CURRENCIES)
    assert len(SITE_MARKETPLACE_DOMAINS) == 19
    assert SITE_MARKETPLACE_DOMAINS["CBT"] == "mercadolibre.com"


@pytest.mark.asyncio
async def test_exchange_code_posts_oauth_payload():
    requests = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "access_token": "access-token",
                "refresh_token": "refresh-token",
                "expires_in": 21600,
                "user_id": 123,
            },
        )

    transport = httpx.MockTransport(handler)
    client = MercadoLibreOAuthClient(
        client_id="client-123",
        client_secret="secret-456",
        redirect_uri="http://localhost:8000/api/stores/meli/callback",
        transport=transport,
    )

    token = await client.exchange_code("code-789")

    assert token.access_token == "access-token"
    assert token.refresh_token == "refresh-token"
    assert token.user_id == 123
    assert requests[0].url == "https://api.mercadolibre.com/oauth/token"
    body = requests[0].content.decode()
    assert "grant_type=authorization_code" in body
    assert "client_id=client-123" in body
    assert "client_secret=secret-456" in body
    assert "code=code-789" in body


@pytest.mark.asyncio
async def test_refresh_token_posts_refresh_payload():
    requests = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "access_token": "new-access-token",
                "refresh_token": "new-refresh-token",
                "expires_in": 21600,
                "user_id": 123,
            },
        )

    transport = httpx.MockTransport(handler)
    client = MercadoLibreOAuthClient(
        client_id="client-123",
        client_secret="secret-456",
        redirect_uri="http://localhost:8000/api/stores/meli/callback",
        transport=transport,
    )

    token = await client.refresh_token("old-refresh-token")

    assert token.access_token == "new-access-token"
    assert token.refresh_token == "new-refresh-token"
    body = requests[0].content.decode()
    assert "grant_type=refresh_token" in body
    assert "client_id=client-123" in body
    assert "client_secret=secret-456" in body
    assert "refresh_token=old-refresh-token" in body
