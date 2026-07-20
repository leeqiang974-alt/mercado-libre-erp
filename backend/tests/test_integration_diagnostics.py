from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.audit_event import AuditEvent
from app.models.registry import import_all_models
from app.models.store import Store
from app.models.token_credential import TokenCredential
from app.schemas.integrations import IntegrationCredentialsUpdate
from app.services.integration_credentials import update_integration_credentials
from app.services.integration_diagnostics import run_integration_diagnostics
from app.services.meli.oauth import MercadoLibreToken
from app.services.meli.token_vault import upsert_store_token


def make_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    import_all_models()
    Base.metadata.create_all(engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def save_credentials(db, settings, **values):
    update_integration_credentials(
        db,
        IntegrationCredentialsUpdate(
            **{key: SecretStr(value) for key, value in values.items()}
        ),
        settings,
        "diagnostic-test-operation",
    )


@pytest.mark.asyncio
async def test_integration_diagnostics_verify_models_and_store_without_exposing_secrets(
    monkeypatch,
):
    settings = get_settings()
    monkeypatch.setattr(settings, "token_encryption_key", "diagnostic-test-key")
    testing_session = make_session()
    with testing_session() as db:
        save_credentials(
            db,
            settings,
            meli_client_id="meli-client-secret-value",
            meli_client_secret="meli-app-secret-value",
            claude_api_key="claude-secret-value",
            nvidia_api_key="nvidia-secret-value",
        )
        store = Store(
            site_id="MLM",
            seller_id="seller-1",
            display_name="Seller One",
            oauth_status="connected",
        )
        db.add(store)
        db.flush()
        upsert_store_token(
            db,
            store,
            MercadoLibreToken(
                access_token="meli-access-secret-value",
                refresh_token="meli-refresh-secret-value",
                expires_in=3600,
                user_id="seller-1",
            ),
            settings.token_encryption_key,
        )
        db.commit()

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.anthropic.com":
            assert request.headers["x-api-key"] == "claude-secret-value"
            return httpx.Response(200, json={"data": [{"id": settings.claude_model}]})
        if request.url.host == "integrate.api.nvidia.com":
            assert request.headers["authorization"] == "Bearer nvidia-secret-value"
            return httpx.Response(200, json={"data": [{"id": settings.nvidia_model}]})
        assert request.url.path == "/users/me"
        assert request.headers["authorization"] == "Bearer meli-access-secret-value"
        return httpx.Response(200, json={"id": "seller-1", "site_id": "MLM"})

    with testing_session() as db:
        result = await run_integration_diagnostics(
            db,
            settings,
            transport=httpx.MockTransport(handler),
        )

    statuses = {(item.provider, item.subject): item.status for item in result.results}
    assert statuses == {
        ("mercado_libre", "application"): "configured",
        ("claude", "claude"): "verified",
        ("nvidia", "nvidia"): "verified",
        ("mercado_libre", "store:1"): "verified",
    }
    serialized = result.model_dump_json()
    for secret in (
        "meli-client-secret-value",
        "meli-app-secret-value",
        "claude-secret-value",
        "nvidia-secret-value",
        "meli-access-secret-value",
        "meli-refresh-secret-value",
    ):
        assert secret not in serialized
    with testing_session() as db:
        audit = (
            db.query(AuditEvent)
            .filter(AuditEvent.action == "integrations.diagnostics.completed")
            .one()
        )
        assert all("secret-value" not in str(item) for item in audit.after_json["results"])


@pytest.mark.asyncio
async def test_integration_diagnostics_do_not_call_network_without_credentials():
    settings = get_settings()
    testing_session = make_session()
    network_calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal network_calls
        network_calls += 1
        return httpx.Response(500)

    with testing_session() as db:
        result = await run_integration_diagnostics(
            db,
            settings,
            transport=httpx.MockTransport(handler),
        )

    assert network_calls == 0
    assert [(item.provider, item.status) for item in result.results] == [
        ("mercado_libre", "not_configured"),
        ("claude", "not_configured"),
        ("nvidia", "not_configured"),
    ]


@pytest.mark.asyncio
async def test_meli_application_requires_a_connected_store(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "token_encryption_key", "diagnostic-test-key")
    testing_session = make_session()
    with testing_session() as db:
        save_credentials(
            db,
            settings,
            meli_client_id="meli-client-id",
            meli_client_secret="meli-client-secret",
        )
        db.add(
            Store(
                site_id="MLM",
                seller_id="seller-1",
                display_name="Disconnected Seller",
                oauth_status="disconnected",
            )
        )
        db.commit()

    network_calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal network_calls
        network_calls += 1
        return httpx.Response(500)

    with testing_session() as db:
        result = await run_integration_diagnostics(
            db,
            settings,
            transport=httpx.MockTransport(handler),
        )

    assert network_calls == 0
    assert result.results[0].status == "authorization_required"
    assert result.results[0].code == "oauth_authorization_required"
    assert result.results[-1].code == "store_not_connected"


@pytest.mark.asyncio
async def test_integration_diagnostics_classify_provider_failures(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "token_encryption_key", "diagnostic-test-key")
    testing_session = make_session()
    with testing_session() as db:
        save_credentials(
            db,
            settings,
            claude_api_key="bad-claude-key",
            nvidia_api_key="limited-nvidia-key",
        )

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.anthropic.com":
            return httpx.Response(401, json={"error": {"type": "authentication_error"}})
        return httpx.Response(403, json={"detail": "forbidden"})

    with testing_session() as db:
        result = await run_integration_diagnostics(
            db,
            settings,
            transport=httpx.MockTransport(handler),
        )

    by_provider = {item.provider: item for item in result.results}
    assert by_provider["claude"].status == "authentication_failed"
    assert by_provider["nvidia"].status == "permission_denied"


@pytest.mark.asyncio
async def test_claude_model_diagnostic_follows_pagination(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "token_encryption_key", "diagnostic-test-key")
    testing_session = make_session()
    with testing_session() as db:
        save_credentials(db, settings, claude_api_key="claude-key")

    requests = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.url.params["limit"] == "100"
        if len(requests) == 1:
            assert "after_id" not in request.url.params
            return httpx.Response(
                200,
                json={
                    "data": [{"id": "another-model"}],
                    "has_more": True,
                    "last_id": "page-one-last-model",
                },
            )
        assert request.url.params["after_id"] == "page-one-last-model"
        return httpx.Response(
            200,
            json={"data": [{"id": settings.claude_model}], "has_more": False},
        )

    with testing_session() as db:
        result = await run_integration_diagnostics(
            db,
            settings,
            transport=httpx.MockTransport(handler),
        )

    claude = next(item for item in result.results if item.provider == "claude")
    assert claude.status == "verified"
    assert len(requests) == 2


@pytest.mark.asyncio
async def test_integration_diagnostics_distinguish_http_rejection_from_unreachable(
    monkeypatch,
):
    settings = get_settings()
    monkeypatch.setattr(settings, "token_encryption_key", "diagnostic-test-key")
    testing_session = make_session()
    with testing_session() as db:
        save_credentials(
            db,
            settings,
            claude_api_key="claude-key",
            nvidia_api_key="nvidia-key",
        )

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.anthropic.com":
            return httpx.Response(402, json={"error": "payment_required"})
        return httpx.Response(404, json={"detail": "not_found"})

    with testing_session() as db:
        result = await run_integration_diagnostics(
            db,
            settings,
            transport=httpx.MockTransport(handler),
        )

    by_provider = {item.provider: item for item in result.results}
    assert by_provider["claude"].status == "payment_required"
    assert by_provider["claude"].code == "provider_payment_required"
    assert by_provider["nvidia"].status == "request_rejected"
    assert by_provider["nvidia"].code == "provider_request_rejected"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("refresh_response", "expected_status", "expected_code"),
    [
        (
            httpx.Response(400, json={"message": "invalid_grant"}),
            "authorization_required",
            "store_reauthorization_required",
        ),
        (
            httpx.Response(200, json={"access_token": "incomplete"}),
            "invalid_response",
            "token_refresh_response_invalid",
        ),
    ],
)
async def test_store_refresh_failures_are_classified_without_green_app_status(
    monkeypatch,
    refresh_response,
    expected_status,
    expected_code,
):
    settings = get_settings()
    monkeypatch.setattr(settings, "token_encryption_key", "diagnostic-test-key")
    testing_session = make_session()
    with testing_session() as db:
        save_credentials(
            db,
            settings,
            meli_client_id="meli-client-id",
            meli_client_secret="meli-client-secret",
        )
        store = Store(
            site_id="MLM",
            seller_id="seller-1",
            display_name="Seller One",
            oauth_status="connected",
        )
        db.add(store)
        db.flush()
        upsert_store_token(
            db,
            store,
            MercadoLibreToken(
                access_token="expired-access-token",
                refresh_token="refresh-token",
                expires_in=1,
                user_id="seller-1",
            ),
            settings.token_encryption_key,
        )
        db.flush()
        credential = db.query(TokenCredential).one()
        credential.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/oauth/token"
        return refresh_response

    with testing_session() as db:
        result = await run_integration_diagnostics(
            db,
            settings,
            transport=httpx.MockTransport(handler),
        )

    app_result, store_result = result.results[0], result.results[-1]
    assert app_result.status == "authorization_required"
    assert app_result.code == "connected_store_verification_failed"
    assert store_result.status == expected_status
    assert store_result.code == expected_code


@pytest.mark.asyncio
async def test_store_identity_mismatch_prevents_green_app_status(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "token_encryption_key", "diagnostic-test-key")
    testing_session = make_session()
    with testing_session() as db:
        save_credentials(
            db,
            settings,
            meli_client_id="meli-client-id",
            meli_client_secret="meli-client-secret",
        )
        store = Store(
            site_id="MLM",
            seller_id="seller-1",
            display_name="Seller One",
            oauth_status="connected",
        )
        db.add(store)
        db.flush()
        upsert_store_token(
            db,
            store,
            MercadoLibreToken(
                access_token="access-token",
                refresh_token="refresh-token",
                expires_in=3600,
                user_id="seller-1",
            ),
            settings.token_encryption_key,
        )
        db.commit()

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/users/me"
        return httpx.Response(200, json={"id": "another-seller", "site_id": "MLM"})

    with testing_session() as db:
        result = await run_integration_diagnostics(
            db,
            settings,
            transport=httpx.MockTransport(handler),
        )

    assert result.results[0].code == "connected_store_verification_failed"
    assert result.results[-1].code == "store_identity_mismatch"


def test_integration_diagnostics_api_returns_status_only():
    testing_session = make_session()

    def override_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    try:
        response = TestClient(app).post("/api/integrations/diagnostics")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["results"][0]["subject"] == "application"
    assert "sk-ant-" not in response.text
    assert "nvapi-" not in response.text
    assert "client_secret" not in response.text
