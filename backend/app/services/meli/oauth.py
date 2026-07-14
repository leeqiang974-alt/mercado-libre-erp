import base64
import hashlib
import hmac
import secrets
import time
from urllib.parse import urlencode

import httpx
from pydantic import BaseModel


AUTHORIZATION_BASE_URL = "https://auth.mercadolibre.com/authorization"
TOKEN_URL = "https://api.mercadolibre.com/oauth/token"


class MercadoLibreToken(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    user_id: int | str


def create_state_token(secret: str = "local-dev-state-secret") -> str:
    timestamp = str(int(time.time()))
    nonce = secrets.token_urlsafe(24)
    payload = f"{timestamp}.{nonce}"
    signature = _sign_state(payload, secret)
    return f"{payload}.{signature}"


def verify_state_token(
    state: str,
    secret: str = "local-dev-state-secret",
    max_age_seconds: int = 600,
) -> bool:
    try:
        timestamp_text, nonce, signature = state.split(".", 2)
        timestamp = int(timestamp_text)
    except (AttributeError, TypeError, ValueError):
        return False
    payload = f"{timestamp_text}.{nonce}"
    expected_signature = _sign_state(payload, secret)
    if not hmac.compare_digest(signature, expected_signature):
        return False
    age = int(time.time()) - timestamp
    return -60 <= age <= max_age_seconds


def _sign_state(payload: str, secret: str) -> str:
    digest = hmac.new(
        (secret or "local-dev-state-secret").encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def build_authorization_url(client_id: str, redirect_uri: str, state: str) -> str:
    query = urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "state": state,
        }
    )
    return f"{AUTHORIZATION_BASE_URL}?{query}"


class MercadoLibreOAuthClient:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.transport = transport

    async def exchange_code(self, code: str) -> MercadoLibreToken:
        data = {
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "redirect_uri": self.redirect_uri,
        }
        async with httpx.AsyncClient(transport=self.transport, timeout=30) as client:
            response = await client.post(TOKEN_URL, data=data)
            response.raise_for_status()
            return MercadoLibreToken.model_validate(response.json())

    async def refresh_token(self, refresh_token: str) -> MercadoLibreToken:
        data = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": refresh_token,
        }
        async with httpx.AsyncClient(transport=self.transport, timeout=30) as client:
            response = await client.post(TOKEN_URL, data=data)
            response.raise_for_status()
            return MercadoLibreToken.model_validate(response.json())
