import httpx
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
from app.services.meli.category_validation import validate_category_attributes


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


def test_listing_types_use_explicit_standard_catalog_when_api_is_forbidden(monkeypatch):
    async def forbidden(client, site_id: str):
        request = httpx.Request("GET", f"https://api.mercadolibre.com/sites/{site_id}/listing_types")
        response = httpx.Response(403, request=request)
        raise httpx.HTTPStatusError("forbidden", request=request, response=response)

    monkeypatch.setattr(metadata, "fetch_listing_type_ids", forbidden)
    client, testing_session = make_client()

    response = client.get("/api/metadata/sites/MLM/listing-types")

    assert response.status_code == 200
    assert response.json() == {
        "listing_type_ids": ["gold_special", "gold_pro"],
        "source": "standard_catalog",
        "verified": False,
    }
    with testing_session() as db:
        assert db.query(MeliMetadataCache).count() == 0


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


def test_live_publish_requires_verified_category_metadata():
    _, testing_session = make_client()

    with testing_session() as db:
        errors = validate_category_attributes(
            db,
            "MLM123",
            [{"id": "BRAND", "value_name": "Acme"}],
            require_verified_metadata=True,
        )

    assert errors == ["category_attributes_not_verified"]


def test_legacy_verified_cache_with_malformed_definition_fails_closed():
    _, testing_session = make_client()
    with testing_session() as db:
        db.add(
            MeliMetadataCache(
                cache_key="category_attributes:MLM123",
                payload_json={
                    "verified": True,
                    "attributes": [{"tags": {"required": True}}],
                },
            )
        )
        db.commit()

        errors = validate_category_attributes(
            db,
            "MLM123",
            [],
            require_verified_metadata=True,
        )

    assert errors == ["category_attributes_not_verified"]


def test_category_validation_checks_catalog_required_ids_and_enumerated_value_ids():
    _, testing_session = make_client()
    with testing_session() as db:
        db.add(
            MeliMetadataCache(
                cache_key="category_attributes:MLM123",
                payload_json={
                    "verified": True,
                    "attributes": [
                        {
                            "id": "COLOR",
                            "tags": {"catalog_required": True},
                            "values": [{"id": "52028", "name": "Blue"}],
                        },
                        {"id": "BRAND", "tags": {"required": True}},
                    ]
                },
            )
        )
        db.commit()

        errors = validate_category_attributes(
            db,
            "MLM123",
            [
                {"id": "COLOR", "value_id": "not-a-color", "value_name": "Blue"},
                {"id": "UNKNOWN", "value_name": "value"},
            ],
            require_verified_metadata=True,
        )

    assert errors == [
        "required_category_attribute_missing:BRAND",
        "category_attribute_value_id_invalid:COLOR",
        "category_attribute_unknown:UNKNOWN",
    ]


def test_category_validation_requires_canonical_list_value_contract():
    _, testing_session = make_client()
    with testing_session() as db:
        db.add(
            MeliMetadataCache(
                cache_key="category_attributes:MLM123",
                payload_json={
                    "verified": True,
                    "attributes": [
                        {
                            "id": "COLOR",
                            "value_type": "list",
                            "values": [{"id": "52028", "name": "Blue"}],
                            "tags": {},
                        },
                        {
                            "id": "SIZE",
                            "value_type": "list",
                            "values": [{"id": "S", "name": "Small"}],
                            "tags": {"variation_attribute": True},
                        },
                    ],
                },
            )
        )
        db.commit()

        missing_id = validate_category_attributes(
            db,
            "MLM123",
            [{"id": "COLOR", "value_name": "Blue"}],
            require_verified_metadata=True,
        )
        mismatched_name = validate_category_attributes(
            db,
            "MLM123",
            [{"id": "COLOR", "value_id": "52028", "value_name": "Black"}],
            require_verified_metadata=True,
        )
        custom_variation = validate_category_attributes(
            db,
            "MLM123",
            [{"id": "SIZE", "value_name": "32 oz"}],
            require_verified_metadata=True,
        )

    assert missing_id == ["category_attribute_value_id_required:COLOR"]
    assert mismatched_name == ["category_attribute_value_name_mismatch:COLOR"]
    assert custom_variation == []


def test_category_validation_rejects_value_id_without_verifiable_values():
    _, testing_session = make_client()
    with testing_session() as db:
        db.add(
            MeliMetadataCache(
                cache_key="category_attributes:MLM123",
                payload_json={
                    "verified": True,
                    "attributes": [
                        {"id": "COLOR", "value_type": "list", "values": [], "tags": {}},
                    ],
                },
            )
        )
        db.commit()

        errors = validate_category_attributes(
            db,
            "MLM123",
            [{"id": "COLOR", "value_id": "bogus"}],
            require_verified_metadata=True,
        )

    assert errors == ["category_attribute_value_id_unverifiable:COLOR"]
