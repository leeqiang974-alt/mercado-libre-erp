from fastapi.testclient import TestClient
import httpx
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

    response = client.post("/api/metadata/sites/MLM/listing-types/refresh")

    assert response.status_code == 200
    assert response.json()["listing_type_ids"] == ["gold_special", "gold_pro"]


def test_metadata_listing_types_default_to_non_blocking_standard_catalog():
    client = make_client()

    response = client.get("/api/metadata/sites/MLM/listing-types")

    assert response.status_code == 200
    assert response.json() == {
        "listing_type_ids": ["gold_special", "gold_pro"],
        "source": "standard_catalog",
        "verified": False,
    }


def test_metadata_routes_proxy_category_prediction(monkeypatch):
    async def fake_predict(client, site_id: str, query: str):
        assert site_id == "MLM"
        assert query == "water bottle"
        return [{"category_id": "MLM123", "category_name": "Moldes"}]

    monkeypatch.setattr(metadata, "predict_category", fake_predict)
    client = make_client()

    response = client.get("/api/metadata/sites/MLM/category-predictions?q=water%20bottle")

    assert response.status_code == 200
    assert response.json()["predictions"][0]["category_id"] == "MLM123"
    assert response.json()["predictions"][0]["category_name_zh"] == "模具"


def test_metadata_routes_expose_upstream_prediction_failure_as_503(monkeypatch):
    async def failed_predict(client, site_id: str, query: str):
        raise httpx.HTTPStatusError(
            "forbidden",
            request=httpx.Request("GET", "https://api.mercadolibre.com"),
            response=httpx.Response(403),
        )

    monkeypatch.setattr(metadata, "predict_category", failed_predict)
    client = make_client()

    response = client.get("/api/metadata/sites/MLM/category-predictions?q=bottle")

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "meli_metadata_unavailable"


def test_metadata_routes_proxy_category_attributes(monkeypatch):
    async def fake_attributes(client, category_id: str):
        assert category_id == "MLM123"
        return [{"id": "BRAND", "name": "Brand"}]

    monkeypatch.setattr(metadata, "fetch_category_attributes", fake_attributes)
    client = make_client()

    response = client.get("/api/metadata/categories/MLM123/attributes")

    assert response.status_code == 200
    assert response.json()["attributes"][0]["id"] == "BRAND"


def test_metadata_routes_reject_malformed_category_attributes(monkeypatch):
    async def malformed_attributes(client, category_id: str):
        raise ValueError("invalid_category_attributes_response")

    monkeypatch.setattr(metadata, "fetch_category_attributes", malformed_attributes)
    client = make_client()

    response = client.get("/api/metadata/categories/MLM123/attributes")

    assert response.status_code == 503
    assert response.json()["detail"] == {
        "code": "meli_metadata_unavailable",
        "operation": "category attributes",
    }


def test_metadata_routes_verify_leaf_category(monkeypatch):
    async def fake_details(client, category_id: str):
        assert category_id == "MLM123"
        return {
            "id": "MLM123",
            "name": "Muffin Pans",
            "path_from_root": [{"id": "MLM1", "name": "Kitchen"}, {"id": "MLM123", "name": "Muffin Pans"}],
            "leaf": True,
        }

    monkeypatch.setattr(metadata, "fetch_category_details", fake_details)
    client = make_client()

    response = client.get("/api/metadata/categories/MLM123")

    assert response.status_code == 200
    assert response.json()["leaf"] is True
    assert response.json()["path_from_root"][-1]["name"] == "Muffin Pans"
    assert response.json()["name_zh"] == "玛芬烤盘"
    assert response.json()["path_from_root_zh"][-1]["name_zh"] == "玛芬烤盘"
