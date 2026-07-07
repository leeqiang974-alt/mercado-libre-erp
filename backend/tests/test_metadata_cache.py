from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import metadata
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.meli_metadata_cache import MeliMetadataCache
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
    return TestClient(app), testing_session


def teardown_function():
    app.dependency_overrides.clear()


def test_listing_types_are_cached_after_refresh(monkeypatch):
    async def fake_fetch(client, site_id: str):
        assert site_id == "MLM"
        return ["gold_special", "gold_pro"]

    monkeypatch.setattr(metadata, "fetch_listing_type_ids", fake_fetch)
    client, testing_session = make_client()

    response = client.post("/api/metadata/sites/MLM/listing-types/refresh")

    assert response.status_code == 200
    assert response.json()["listing_type_ids"] == ["gold_special", "gold_pro"]
    with testing_session() as db:
        cache = db.query(MeliMetadataCache).one()
        assert cache.cache_key == "listing_types:MLM"
        assert cache.payload_json["listing_type_ids"] == ["gold_special", "gold_pro"]


def test_listing_types_read_uses_cache_without_fetching(monkeypatch):
    async def fake_fetch(client, site_id: str):
        raise AssertionError("fetch should not run when cache exists")

    monkeypatch.setattr(metadata, "fetch_listing_type_ids", fake_fetch)
    client, testing_session = make_client()
    with testing_session() as db:
        db.add(
            MeliMetadataCache(
                cache_key="listing_types:MLM",
                payload_json={"listing_type_ids": ["gold_special"]},
            )
        )
        db.commit()

    response = client.get("/api/metadata/sites/MLM/listing-types")

    assert response.status_code == 200
    assert response.json()["listing_type_ids"] == ["gold_special"]


def test_category_attributes_are_cached_after_refresh(monkeypatch):
    async def fake_attributes(client, category_id: str):
        assert category_id == "MLM123"
        return [{"id": "BRAND", "name": "Brand"}]

    monkeypatch.setattr(metadata, "fetch_category_attributes", fake_attributes)
    client, testing_session = make_client()

    response = client.post("/api/metadata/categories/MLM123/attributes/refresh")

    assert response.status_code == 200
    assert response.json()["attributes"][0]["id"] == "BRAND"
    with testing_session() as db:
        cache = db.query(MeliMetadataCache).one()
        assert cache.cache_key == "category_attributes:MLM123"
        assert cache.payload_json["attributes"][0]["name"] == "Brand"
