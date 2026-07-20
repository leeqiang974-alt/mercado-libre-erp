from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import integrations, publishing, reviews
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.audit_event import AuditEvent
from app.models.integration_credential import IntegrationCredential
from app.models.registry import import_all_models
from app.schemas.reviews import ReviewResponse
from app.services.meli.token_vault import decrypt_token_value
from app.workers import publish_worker


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


def teardown_client() -> None:
    app.dependency_overrides.clear()


def test_credentials_api_encrypts_values_and_never_returns_secrets(monkeypatch):
    monkeypatch.setattr(integrations.settings, "token_encryption_key", "credential-test-key")
    client, testing_session = make_client()
    secrets = {
        "meli_client_id": "meli-client-123",
        "meli_client_secret": "meli-secret-456",
        "claude_api_key": "sk-ant-secret",
        "nvidia_api_key": "nvapi-secret",
    }
    try:
        operation_id = "0cebdc44-ae5e-48d9-80e2-6d43c8c74d35"
        response = client.put(
            "/api/integrations/credentials",
            json=secrets,
            headers={"X-Integration-Operation-ID": operation_id},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["meli_client_id_configured"] is True
        assert body["meli_client_secret_configured"] is True
        assert body["claude_api_key_configured"] is True
        assert body["nvidia_api_key_configured"] is True
        assert all(secret not in response.text for secret in secrets.values())
        with testing_session() as db:
            rows = db.query(IntegrationCredential).all()
            assert len(rows) == 4
            for row in rows:
                assert row.last_operation_id == operation_id
                assert secrets[row.credential_key] not in row.encrypted_value
                assert (
                    decrypt_token_value(row.encrypted_value, "credential-test-key")
                    == secrets[row.credential_key]
                )
            audit = db.query(AuditEvent).one()
            assert audit.after_json == {
                "changed_keys": list(secrets),
                "operation_id": operation_id,
            }
            assert all(secret not in str(audit.after_json) for secret in secrets.values())
    finally:
        teardown_client()


def test_credentials_api_rejects_invalid_operation_id(monkeypatch):
    monkeypatch.setattr(integrations.settings, "token_encryption_key", "credential-test-key")
    client, testing_session = make_client()
    try:
        response = client.put(
            "/api/integrations/credentials",
            json={"claude_api_key": "secret"},
            headers={"X-Integration-Operation-ID": "not-a-uuid"},
        )

        assert response.status_code == 400
        with testing_session() as db:
            assert db.query(IntegrationCredential).count() == 0
            assert db.query(AuditEvent).count() == 0
    finally:
        teardown_client()


def test_empty_saved_value_overrides_environment_fallback(monkeypatch):
    monkeypatch.setattr(integrations.settings, "token_encryption_key", "credential-test-key")
    monkeypatch.setattr(integrations.settings, "claude_api_key", "environment-claude-key")
    client, _ = make_client()
    try:
        assert client.get("/api/integrations/credentials").json()["claude_api_key_configured"]

        response = client.put(
            "/api/integrations/credentials",
            json={"claude_api_key": ""},
        )

        assert response.status_code == 200
        assert response.json()["claude_api_key_configured"] is False
        assert client.get("/api/integrations/credentials").json()[
            "claude_api_key_configured"
        ] is False
    finally:
        teardown_client()


def test_saved_credentials_feed_meli_oauth_ai_route_and_publish_worker(monkeypatch):
    monkeypatch.setattr(integrations.settings, "token_encryption_key", "credential-test-key")
    monkeypatch.setattr(integrations.settings, "meli_client_id", "")
    monkeypatch.setattr(integrations.settings, "meli_client_secret", "")
    monkeypatch.setattr(integrations.settings, "claude_api_key", "")
    client, testing_session = make_client()
    captured = {}

    class CapturingClaudeClient:
        def __init__(self, api_key: str, model: str = ""):
            captured["claude_api_key"] = api_key

        async def review_draft(self, draft):
            return ReviewResponse(
                provider="claude",
                decision="pass",
                risk_level="low",
                reason_codes=[],
                reasons=[],
            )

    monkeypatch.setattr(reviews, "ClaudeReviewClient", CapturingClaudeClient)
    try:
        client.put(
            "/api/integrations/credentials",
            json={
                "meli_client_id": "saved-meli-client",
                "meli_client_secret": "saved-meli-secret",
                "claude_api_key": "saved-claude-key",
            },
        )

        readiness = client.get("/api/system/readiness")
        assert readiness.status_code == 200
        assert readiness.json()["mercado_libre"]["credentials_configured"] is True
        assert readiness.json()["ai"]["claude_configured"] is True
        assert "saved-claude-key" not in readiness.text

        authorization = client.get("/api/stores/meli/authorization-url")
        assert authorization.status_code == 200
        assert "client_id=saved-meli-client" in authorization.json()["authorization_url"]
        review = client.post(
            "/api/reviews/claude",
            json={
                "title": "Bottle",
                "description": "Leak proof.",
                "target_site_id": "MLM",
                "price": 99,
                "currency": "MXN",
                "stock": 1,
                "image_urls": ["https://example.com/a.jpg"],
            },
        )
        assert review.status_code == 200
        assert captured["claude_api_key"] == "saved-claude-key"
        with testing_session() as db:
            route_oauth_client = publishing.create_oauth_client(db)
            assert route_oauth_client.client_id == "saved-meli-client"
            assert route_oauth_client.client_secret == "saved-meli-secret"
            oauth_client = publish_worker._create_oauth_client(db)
            assert oauth_client.client_id == "saved-meli-client"
            assert oauth_client.client_secret == "saved-meli-secret"
    finally:
        teardown_client()
