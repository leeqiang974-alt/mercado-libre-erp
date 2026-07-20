from fastapi.testclient import TestClient
import pytest

from app.api.routes import reviews
from app.main import app
from app.schemas.reviews import ReviewResponse
from app.services.integration_credentials import ResolvedIntegrationCredentials


@pytest.fixture(autouse=True)
def resolve_credentials_from_test_settings(monkeypatch):
    monkeypatch.setattr(
        reviews,
        "resolve_integration_credentials",
        lambda db, settings: ResolvedIntegrationCredentials(
            meli_client_id=settings.meli_client_id,
            meli_client_secret=settings.meli_client_secret,
            claude_api_key=settings.claude_api_key,
            nvidia_api_key=settings.nvidia_api_key,
        ),
    )


def draft_payload():
    return {
        "title": "Bottle",
        "description": "Leak proof.",
        "target_site_id": "MLM",
        "price": 9.99,
        "currency": "USD",
        "stock": 1,
        "image_urls": ["https://example.com/a.jpg"],
    }


def test_claude_review_route_uses_client_without_echoing_key(monkeypatch):
    class FakeClaudeClient:
        def __init__(self, api_key: str, model: str = ""):
            assert api_key == "claude-secret"

        async def review_draft(self, draft):
            return ReviewResponse(
                provider="claude",
                decision="pass",
                risk_level="low",
                reason_codes=[],
                reasons=["ok"],
            )

    monkeypatch.setattr(reviews.settings, "claude_api_key", "claude-secret")
    monkeypatch.setattr(reviews, "ClaudeReviewClient", FakeClaudeClient)
    client = TestClient(app)

    response = client.post("/api/reviews/claude", json=draft_payload())

    assert response.status_code == 200
    assert response.json()["provider"] == "claude"
    assert "claude-secret" not in response.text


def test_nvidia_review_route_uses_client_without_echoing_key(monkeypatch):
    class FakeNvidiaClient:
        def __init__(self, api_key: str, model: str = ""):
            assert api_key == "nvidia-secret"

        async def pre_screen_draft(self, draft):
            return ReviewResponse(
                provider="nvidia",
                decision="needs_human_review",
                risk_level="medium",
                reason_codes=["brand_risk"],
                reasons=["verify"],
            )

    monkeypatch.setattr(reviews.settings, "nvidia_api_key", "nvidia-secret")
    monkeypatch.setattr(reviews, "NvidiaReviewClient", FakeNvidiaClient)
    client = TestClient(app)

    response = client.post("/api/reviews/nvidia", json=draft_payload())

    assert response.status_code == 200
    assert response.json()["provider"] == "nvidia"
    assert "nvidia-secret" not in response.text


def test_behavioral_audit_runs_both_providers_and_aggregates_the_strictest_result(monkeypatch):
    calls = []

    class FakeClaudeClient:
        def __init__(self, api_key: str, model: str = ""):
            assert api_key == "claude-secret"

        async def review_draft(self, draft):
            calls.append("claude")
            return ReviewResponse(
                provider="claude",
                decision="needs_human_review",
                risk_level="medium",
                reason_codes=["brand_risk"],
                reasons=["verify brand claim"],
                input_tokens=100,
                output_tokens=20,
                total_tokens=120,
            )

    class FakeNvidiaClient:
        def __init__(self, api_key: str, model: str = ""):
            assert api_key == "nvidia-secret"

        async def pre_screen_draft(self, draft):
            calls.append("nvidia")
            return ReviewResponse(
                provider="nvidia",
                decision="block",
                risk_level="high",
                reason_codes=["restricted_item"],
                reasons=["restricted"],
                input_tokens=80,
                output_tokens=10,
                total_tokens=90,
            )

    monkeypatch.setattr(reviews.settings, "claude_api_key", "claude-secret")
    monkeypatch.setattr(reviews.settings, "nvidia_api_key", "nvidia-secret")
    monkeypatch.setattr(reviews, "ClaudeReviewClient", FakeClaudeClient)
    monkeypatch.setattr(reviews, "NvidiaReviewClient", FakeNvidiaClient)

    response = TestClient(app).post("/api/reviews/behavioral-audit", json=draft_payload())

    assert response.status_code == 200
    body = response.json()
    assert calls == ["nvidia", "claude"]
    assert body["nvidia"]["decision"] == "block"
    assert body["claude"]["decision"] == "needs_human_review"
    assert body["aggregate"]["provider"] == "claude+nvidia_behavioral_audit"
    assert body["aggregate"]["decision"] == "block"
    assert body["aggregate"]["risk_level"] == "high"
    assert body["aggregate"]["reason_codes"] == ["restricted_item", "brand_risk"]
    assert body["aggregate"]["input_tokens"] == 180
    assert body["aggregate"]["output_tokens"] == 30
    assert body["aggregate"]["total_tokens"] == 210


def test_provider_route_reports_missing_key_instead_of_local_fallback(monkeypatch):
    monkeypatch.setattr(reviews.settings, "claude_api_key", "")

    response = TestClient(app).post("/api/reviews/claude", json=draft_payload())

    assert response.status_code == 503
    assert response.json()["detail"] == {
        "provider": "claude",
        "code": "api_key_required",
        "retryable": False,
        "retry_after_seconds": None,
        "request_id": "",
        "provider_http_status": None,
    }
    assert "fallback" not in response.text


def test_provider_route_exposes_rate_limit_without_automatic_retry(monkeypatch):
    calls = 0

    class RateLimitedClaudeClient:
        def __init__(self, api_key: str, model: str = ""):
            pass

        async def review_draft(self, draft):
            nonlocal calls
            calls += 1
            from app.services.ai.provider_utils import AIProviderError

            raise AIProviderError(
                "claude",
                "rate_limited",
                http_status=429,
                retryable=True,
                retry_after_seconds=23,
                request_id="req_rate_limited",
            )

    monkeypatch.setattr(reviews.settings, "claude_api_key", "configured")
    monkeypatch.setattr(reviews, "ClaudeReviewClient", RateLimitedClaudeClient)

    response = TestClient(app).post("/api/reviews/claude", json=draft_payload())

    assert response.status_code == 429
    assert calls == 1
    assert response.json()["detail"] == {
        "provider": "claude",
        "code": "rate_limited",
        "retryable": True,
        "retry_after_seconds": 23,
        "request_id": "req_rate_limited",
        "provider_http_status": 429,
    }


def test_provider_route_preserves_non_rate_limit_upstream_status(monkeypatch):
    class RejectedNvidiaClient:
        def __init__(self, api_key: str, model: str = ""):
            pass

        async def pre_screen_draft(self, draft):
            from app.services.ai.provider_utils import AIProviderError

            raise AIProviderError(
                "nvidia",
                "authentication_failed",
                http_status=401,
                request_id="req_nvidia_401",
            )

    monkeypatch.setattr(reviews.settings, "nvidia_api_key", "configured")
    monkeypatch.setattr(reviews, "NvidiaReviewClient", RejectedNvidiaClient)

    response = TestClient(app).post("/api/reviews/nvidia", json=draft_payload())

    assert response.status_code == 502
    assert response.json()["detail"]["provider_http_status"] == 401
    assert response.json()["detail"]["request_id"] == "req_nvidia_401"
