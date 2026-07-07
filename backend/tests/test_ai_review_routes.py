from fastapi.testclient import TestClient

from app.api.routes import reviews
from app.main import app
from app.schemas.reviews import ReviewResponse


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
        def __init__(self, api_key: str):
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
        def __init__(self, api_key: str):
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
