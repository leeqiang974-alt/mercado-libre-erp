from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import metadata
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.registry import import_all_models


def make_client():
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
    return TestClient(app)


def teardown_function():
    app.dependency_overrides.clear()


def test_metadata_routes_proxy_listing_types(monkeypatch):
    async def fake_fetch(client, site_id: str):
        assert site_id == "MLM"
        return ["gold_special", "gold_pro"]

    monkeypatch.setattr(metadata, "fetch_listing_type_ids", fake_fetch)
    client = make_client()

    response = client.get("/api/metadata/sites/MLM/listing-types")

    assert response.status_code == 200
    assert response.json()["listing_type_ids"] == ["gold_special", "gold_pro"]


def test_metadata_routes_proxy_category_prediction(monkeypatch):
    async def fake_predict(client, site_id: str, query: str):
        assert site_id == "MLM"
        assert query == "water bottle"
        return [{"category_id": "MLM123", "category_name": "Bottles"}]

    monkeypatch.setattr(metadata, "predict_category", fake_predict)
    client = make_client()

    response = client.get("/api/metadata/sites/MLM/category-predictions?q=water%20bottle")

    assert response.status_code == 200
    assert response.json()["predictions"][0]["category_id"] == "MLM123"


def test_metadata_routes_proxy_category_attributes(monkeypatch):
    async def fake_attributes(client, category_id: str):
        assert category_id == "MLM123"
        return [{"id": "BRAND", "name": "Brand"}]

    monkeypatch.setattr(metadata, "fetch_category_attributes", fake_attributes)
    client = make_client()

    response = client.get("/api/metadata/categories/MLM123/attributes")

    assert response.status_code == 200
    assert response.json()["attributes"][0]["id"] == "BRAND"
