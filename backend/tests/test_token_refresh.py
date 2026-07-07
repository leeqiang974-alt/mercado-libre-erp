from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.registry import import_all_models
from app.models.store import Store
from app.models.token_credential import TokenCredential
from app.services.meli.oauth import MercadoLibreOAuthClient
from app.services.meli.token_vault import (
    decrypt_token_value,
    encrypt_token_value,
    resolve_fresh_store_access_token,
)


def make_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    import_all_models()
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return testing_session


@pytest.mark.asyncio
async def test_resolve_fresh_store_access_token_refreshes_expiring_credentials():
    testing_session = make_session()
    with testing_session() as db:
        store = Store(
            site_id="MLM",
            seller_id="seller-1",
            display_name="Demo Store",
            oauth_status="connected",
            token_reference="meli:seller-1",
        )
        db.add(store)
        db.flush()
        db.add(
            TokenCredential(
                store_id=store.id,
                token_reference="meli:seller-1",
                encrypted_access_token=encrypt_token_value("old-access-token", "test-secret"),
                encrypted_refresh_token=encrypt_token_value("old-refresh-token", "test-secret"),
                expires_at=datetime.now(UTC) + timedelta(seconds=30),
            )
        )
        db.commit()

    requests = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "access_token": "new-access-token",
                "refresh_token": "new-refresh-token",
                "expires_in": 21600,
                "user_id": "seller-1",
            },
        )

    client = MercadoLibreOAuthClient(
        client_id="client-123",
        client_secret="secret-456",
        redirect_uri="http://localhost:8000/api/stores/meli/callback",
        transport=httpx.MockTransport(handler),
    )
    with testing_session() as db:
        store = db.get(Store, 1)
        access_token = await resolve_fresh_store_access_token(
            db=db,
            store=store,
            encryption_key="test-secret",
            oauth_client=client,
            refresh_window_seconds=300,
        )

    assert access_token == "new-access-token"
    assert len(requests) == 1
    with testing_session() as db:
        credential = db.query(TokenCredential).one()
        assert "new-access-token" not in credential.encrypted_access_token
        assert "new-refresh-token" not in credential.encrypted_refresh_token
        assert decrypt_token_value(credential.encrypted_access_token, "test-secret") == "new-access-token"
        assert decrypt_token_value(credential.encrypted_refresh_token, "test-secret") == "new-refresh-token"


@pytest.mark.asyncio
async def test_resolve_fresh_store_access_token_keeps_valid_credentials():
    testing_session = make_session()
    with testing_session() as db:
        store = Store(
            site_id="MLM",
            seller_id="seller-1",
            display_name="Demo Store",
            oauth_status="connected",
            token_reference="meli:seller-1",
        )
        db.add(store)
        db.flush()
        db.add(
            TokenCredential(
                store_id=store.id,
                token_reference="meli:seller-1",
                encrypted_access_token=encrypt_token_value("valid-access-token", "test-secret"),
                encrypted_refresh_token=encrypt_token_value("valid-refresh-token", "test-secret"),
                expires_at=datetime.now(UTC) + timedelta(hours=2),
            )
        )
        db.commit()

    async def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("refresh should not run")

    client = MercadoLibreOAuthClient(
        client_id="client-123",
        client_secret="secret-456",
        redirect_uri="http://localhost:8000/api/stores/meli/callback",
        transport=httpx.MockTransport(handler),
    )
    with testing_session() as db:
        store = db.get(Store, 1)
        access_token = await resolve_fresh_store_access_token(
            db=db,
            store=store,
            encryption_key="test-secret",
            oauth_client=client,
            refresh_window_seconds=300,
        )

    assert access_token == "valid-access-token"
