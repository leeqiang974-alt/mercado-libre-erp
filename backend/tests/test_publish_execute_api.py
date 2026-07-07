from fastapi.testclient import TestClient

from app.api.routes import publishing
from app.main import app
from app.schemas.publishing import PublishExecutionResult


def payload():
    return {
        "access_token": "secret-token",
        "draft": {
            "title": "Bottle",
            "description": "Leak proof.",
            "target_site_id": "MLM",
            "target_category_id": "MLM123",
            "price": 9.99,
            "currency": "USD",
            "stock": 2,
            "image_urls": ["https://example.com/a.jpg"],
        },
        "review": {
            "provider": "local_policy",
            "decision": "pass",
            "risk_level": "low",
            "reason_codes": [],
            "reasons": [],
            "suggested_changes": {},
        },
        "listing_choice": {
            "site_id": "MLM",
            "listing_type_id": "gold_special",
            "fulfillment": "not_full",
        },
        "valid_listing_type_ids": ["gold_special"],
        "human_approved": True,
    }


def test_publish_execute_route_blocks_by_default():
    client = TestClient(app)
    response = client.post("/api/publishing/execute", json=payload())

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "blocked"
    assert "live_publish_disabled" in body["errors"]
    assert "secret-token" not in response.text


def test_publish_execute_route_uses_service_without_echoing_token(monkeypatch):
    async def fake_execute_publish(**kwargs):
        assert kwargs["client"].access_token == "secret-token"
        return PublishExecutionResult(
            status="published",
            item_id="MLM123",
            permalink="https://example.com/MLM123",
        )

    monkeypatch.setattr(publishing.settings, "allow_live_publish", True)
    monkeypatch.setattr(publishing, "execute_publish", fake_execute_publish)
    client = TestClient(app)

    response = client.post("/api/publishing/execute", json=payload())

    assert response.status_code == 200
    assert response.json()["item_id"] == "MLM123"
    assert "secret-token" not in response.text
