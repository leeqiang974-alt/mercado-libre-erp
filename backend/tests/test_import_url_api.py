from fastapi.testclient import TestClient

from app.api.routes import imports
from app.main import app
from app.schemas.drafts import ProductDraftCreate
from app.services.amazon.collector import CollectionResult, CollectionStatus


def test_import_amazon_url_returns_draft(monkeypatch):
    async def fake_collect(source_url: str, target_site_id: str):
        return CollectionResult(
            status=CollectionStatus.COLLECTED,
            source_url=source_url,
            message="collected",
            draft=ProductDraftCreate(
                title="URL Bottle",
                target_site_id=target_site_id,
                price=10,
                currency="USD",
                stock=1,
                image_urls=["https://example.com/a.jpg"],
            ),
        )

    monkeypatch.setattr(imports, "collect_amazon_page", fake_collect)
    client = TestClient(app)
    response = client.post(
        "/api/imports/amazon-url",
        json={"source_url": "https://www.amazon.com/dp/B000TEST01", "target_site_id": "MLM"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "collected"
    assert body["draft"]["title"] == "URL Bottle"


def test_import_amazon_url_returns_manual_action(monkeypatch):
    async def fake_collect(source_url: str, target_site_id: str):
        return CollectionResult(
            status=CollectionStatus.NEEDS_MANUAL_ACTION,
            source_url=source_url,
            message="Amazon challenge detected; manual action required.",
            draft=None,
        )

    monkeypatch.setattr(imports, "collect_amazon_page", fake_collect)
    client = TestClient(app)
    response = client.post(
        "/api/imports/amazon-url",
        json={"source_url": "https://www.amazon.com/dp/B000TEST01", "target_site_id": "MLM"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "needs_manual_action"
    assert body["draft"] is None
