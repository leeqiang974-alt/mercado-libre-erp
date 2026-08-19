import base64
import hashlib
import hmac
import secrets
import time
from urllib.parse import urlencode

import httpx
from pydantic import BaseModel

from app.services.meli.sites import authorization_base_url

TOKEN_URL = "https://api.mercadolibre.com/oauth/token"


class MercadoLibreToken(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    user_id: int | str


def _generate_code_verifier() -> str:
    """Generate a PKCE code_verifier (43-128 chars, URL-safe)."""
    return secrets.token_urlsafe(64)


def _code_challenge_from_verifier(verifier: str) -> str:
    """Compute PKCE code_challenge = BASE64URL(SHA256(verifier))."""
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def create_state_token(secret: str, site_id: str, code_verifier: str | None = None) -> str:
    timestamp = str(int(time.time()))
    normalized_site_id = site_id.strip().upper()
    authorization_base_url(normalized_site_id)
    nonce = secrets.token_urlsafe(24)
    verifier = code_verifier or _generate_code_verifier()
    payload = f"{timestamp}.{normalized_site_id}.{nonce}.{verifier}"
    signature = _sign_state(payload, secret)
    return f"{payload}.{signature}"


def get_state_code_verifier(state: str, secret: str) -> str | None:
    """Extract code_verifier from a valid state token."""
    try:
        parts = state.split(".")
        if len(parts) < 5:
            return None
        timestamp_text = parts[0]
        site_id = parts[1]
        nonce = parts[2]
        verifier = parts[3]
        signature = ".".join(parts[4:])
        int(timestamp_text)
        authorization_base_url(site_id)
        payload = f"{timestamp_text}.{site_id}.{nonce}.{verifier}"
        expected_signature = _sign_state(payload, secret)
        if not hmac.compare_digest(signature, expected_signature):
            return None
        return verifier
    except (AttributeError, TypeError, ValueError):
        return None


def verify_state_token(
    state: str,
    secret: str = "local-dev-state-secret",
    max_age_seconds: int = 600,
) -> bool:
    return get_state_site_id(state, secret, max_age_seconds=max_age_seconds) is not None


def get_state_site_id(
    state: str,
    secret: str,
    max_age_seconds: int = 600,
) -> str | None:
    try:
        parts = state.split(".")
        if len(parts) < 5:
            # Legacy state without code_verifier (4 parts)
            timestamp_text, site_id, nonce, signature = state.split(".", 3)
            payload = f"{timestamp_text}.{site_id}.{nonce}"
        else:
            timestamp_text = parts[0]
            site_id = parts[1]
            nonce = parts[2]
            signature = ".".join(parts[4:])
            payload = f"{timestamp_text}.{site_id}.{nonce}.{parts[3]}"
        timestamp = int(timestamp_text)
    except (AttributeError, TypeError, ValueError):
        return None
    try:
        authorization_base_url(site_id)
    except ValueError:
        return None
    expected_signature = _sign_state(payload, secret)
    if not hmac.compare_digest(signature, expected_signature):
        return None
    age = int(time.time()) - timestamp
    return site_id if -60 <= age <= max_age_seconds else None


def _sign_state(payload: str, secret: str) -> str:
    digest = hmac.new(
        (secret or "local-dev-state-secret").encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def build_authorization_url(
    client_id: str,
    redirect_uri: str,
    state: str,
    site_id: str,
    code_verifier: str | None = None,
) -> str:
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": state,
        "scope": "read write offline_access orders:read orders:write products:read products:write marketplace:read marketplace:write",
    }
    # PKCE: add code_challenge
    verifier = code_verifier or _generate_code_verifier()
    params["code_challenge"] = _code_challenge_from_verifier(verifier)
    params["code_challenge_method"] = "S256"
    query = urlencode(params)
    return f"{authorization_base_url(site_id)}?{query}"


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

    async def exchange_code(self, code: str, code_verifier: str | None = None) -> MercadoLibreToken:
        data = {
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "redirect_uri": self.redirect_uri,
        }
        if code_verifier:
            data["code_verifier"] = code_verifier
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
