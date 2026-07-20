import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import imports
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.registry import import_all_models
from app.schemas.drafts import ProductDraftCreate
from app.services.amazon.collector import CollectionResult, CollectionStatus


@pytest.fixture(autouse=True)
def database_override():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    import_all_models()
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)


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

    throttled = client.post(
        "/api/imports/amazon-url",
        json={"source_url": "https://amazon.com/dp/B000TEST02", "target_site_id": "MLM"},
    )
    assert throttled.status_code == 429
    assert throttled.json()["detail"] == "amazon_domain_throttled"
    assert int(throttled.headers["Retry-After"]) >= 1


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

    throttled = client.post(
        "/api/imports/amazon-url",
        json={"source_url": "https://amazon.com/dp/B000TEST02", "target_site_id": "MLM"},
    )
    assert throttled.status_code == 429
    assert int(throttled.headers["Retry-After"]) >= 300
