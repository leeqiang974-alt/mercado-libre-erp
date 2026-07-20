import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.audit_event import AuditEvent
from app.models.draft_listing_config import DraftListingConfig
from app.models.product_draft import ProductDraft
from app.models.source_product import SourceProduct, SourceProductStatus
from app.models.meli_metadata_cache import MeliMetadataCache
from app.models.registry import import_all_models
from app.models.review_result import ReviewDecision, ReviewResult
from app.models.store import Store
from app.services import draft_listing_configs
from pricing_test_support import add_current_pricing


def make_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    import_all_models()
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    with testing_session() as db:
        db.add(
            MeliMetadataCache(
                cache_key="category_attributes:MLM123",
                payload_json={
                    "verified": True,
                    "attributes": [
                        {"id": "BRAND", "name": "Brand", "tags": {}},
                        {"id": "MODEL", "name": "Model", "tags": {}},
                        {
                            "id": "COLOR",
                            "name": "Color",
                            "value_type": "list",
                            "values": [{"id": "52028", "name": "Blue"}],
                            "tags": {"variation_attribute": True},
                        },
                    ],
                },
            )
        )
        draft = ProductDraft(
            title="Bottle",
            description="Leak proof.",
            target_site_id="MLM",
            target_category_id="",
            price=9.99,
            currency="MXN",
            stock=2,
            image_urls_json=["https://example.com/a.jpg"],
        )
        db.add(draft)
        db.flush()
        add_current_pricing(db, draft)
        db.add(
            Store(
                site_id="MLM",
                seller_id="seller-1",
                display_name="Test store",
                oauth_status="connected",
            )
        )
        db.commit()

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


def config_payload():
    return {
        "site_id": "MLM",
        "store_id": 1,
        "category_id": "MLM123",
        "listing_type_id": "gold_special",
        "fulfillment": "not_full",
        "shipping_mode": "me2",
        "shipping_logistic_type": "drop_off",
        "attributes": [
            {"id": "BRAND", "value_name": "Acme"},
            {"id": "MODEL", "value_name": "B-100"},
        ],
    }


def review_payload():
    return {
        "provider": "local_policy",
        "decision": "pass",
        "risk_level": "low",
        "reason_codes": [],
        "reasons": [],
        "suggested_changes": {},
    }


def seed_publish_review(testing_session) -> int:
    with testing_session() as db:
        draft = db.get(ProductDraft, 1)
        row = ReviewResult(
            product_draft_id=1,
            provider="claude+nvidia_behavioral_audit",
            prompt_version="meli-behavioral-audit-v2",
            risk_level="low",
            decision=ReviewDecision.PASS,
            reasons_json={"reason_codes": [], "reasons": []},
            suggested_changes_json={},
            draft_version=draft.content_version,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.id


def test_listing_config_can_be_saved_and_read_for_draft():
    client, testing_session = make_client()

    response = client.put("/api/drafts/1/listing-config", json=config_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["product_draft_id"] == 1
    assert body["store_id"] == 1
    assert body["category_id"] == "MLM123"
    assert body["listing_type_id"] == "gold_special"
    assert body["shipping_mode"] == "me2"
    assert body["shipping_logistic_type"] == "drop_off"
    assert body["attributes"][0]["id"] == "BRAND"

    get_response = client.get("/api/drafts/1/listing-config")
    assert get_response.status_code == 200
    assert get_response.json()["attributes"][1]["value_name"] == "B-100"

    with testing_session() as db:
        draft = db.get(ProductDraft, 1)
        assert draft.target_category_id == "MLM123"
        assert draft.listing_type_id == "gold_special"


def test_source_variant_attributes_are_suggested_against_category_metadata():
    client, testing_session = make_client()
    with testing_session() as db:
        draft = db.get(ProductDraft, 1)
        draft.brand = "TrailPro"
        draft.source_variant_asin = "B000TEST02"
        draft.source_variant_attributes_json = {"Color Name": "Blue", "Size": "32 oz"}
        cache = db.query(MeliMetadataCache).one()
        cache.payload_json = {
                    "verified": True,
                    "attributes": [
                        {
                            "id": "COLOR",
                            "name": "Color principal",
                            "value_type": "list",
                            "values": [{"id": "52028", "name": "Blue"}],
                            "tags": {"variation_attribute": True},
                        },
                        {
                            "id": "SIZE",
                            "name": "Talla",
                            "value_type": "list",
                            "values": [{"id": "S", "name": "Small"}],
                            "tags": {"variation_attribute": True, "required": True},
                        },
                        {
                            "id": "BRAND",
                            "name": "Marca",
                            "value_type": "string",
                            "tags": {"required": True},
                        },
                    ],
                }
        db.commit()

    response = client.get(
        "/api/drafts/1/attribute-suggestions?category_id=mlm123"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["source_variant_asin"] == "B000TEST02"
    assert body["listing_strategy"] == "one_source_asin_per_item"
    suggestions = {item["attribute_id"]: item for item in body["suggestions"]}
    assert suggestions["COLOR"] | {
        "value_id": "52028",
        "value_name": "Blue",
        "variation_attribute": True,
        "can_apply": True,
    } == suggestions["COLOR"]
    assert suggestions["SIZE"]["value_name"] == "32 oz"
    assert suggestions["SIZE"]["value_id"] is None
    assert suggestions["SIZE"]["can_apply"] is False
    assert suggestions["BRAND"]["value_name"] == "TrailPro"
    assert suggestions["BRAND"]["can_apply"] is True


def test_attribute_suggestions_require_cached_category_metadata():
    client, testing_session = make_client()
    with testing_session() as db:
        db.query(MeliMetadataCache).delete()
        db.commit()

    response = client.get(
        "/api/drafts/1/attribute-suggestions?category_id=MLM123"
    )

    assert response.status_code == 409
    assert "category_attributes_not_verified" in response.text


def test_attribute_suggestions_do_not_match_modified_semantics():
    client, testing_session = make_client()
    with testing_session() as db:
        draft = db.get(ProductDraft, 1)
        draft.source_variant_attributes_json = {"Color": "Blue", "Size": "32 oz"}
        cache = db.query(MeliMetadataCache).one()
        cache.payload_json = {
            "verified": True,
            "attributes": [
                {"id": "SECONDARY_COLOR", "name": "Secondary color", "tags": {}},
                {"id": "PACKAGE_SIZE", "name": "Package size", "tags": {}},
            ],
        }
        db.commit()

    response = client.get("/api/drafts/1/attribute-suggestions?category_id=MLM123")

    assert response.status_code == 200
    assert response.json()["suggestions"] == []
    assert response.json()["unmatched_source_attributes"] == {
        "Color": "Blue",
        "Size": "32 oz",
    }


def test_selected_source_measurements_are_suggested_conservatively():
    client, testing_session = make_client()
    with testing_session() as db:
        source = SourceProduct(
            source_url="https://amazon.com/dp/B000TEST01",
            asin="B000TEST01",
            raw_status=SourceProductStatus.COLLECTED,
            variants_json=[
                {"asin": "B000TEST01", "attributes": {}, "selected": True},
            ],
            measurements_json={
                "item_weight": {"value": 1.2, "unit": "lb", "raw": "1.2 pounds"},
                "package_dimensions": {
                    "length": 30,
                    "width": 20,
                    "height": 10,
                    "unit": "cm",
                    "raw": "30 x 20 x 10 cm",
                },
            },
        )
        db.add(source)
        db.flush()
        draft = db.get(ProductDraft, 1)
        draft.source_product_id = source.id
        draft.source_variant_asin = "B000TEST01"
        cache = db.query(MeliMetadataCache).one()
        cache.payload_json = {
            "verified": True,
            "attributes": [
                {"id": "WEIGHT", "name": "Weight", "tags": {}},
                {"id": "PACKAGE_LENGTH", "name": "Package length", "tags": {}},
                {"id": "PACKAGE_WIDTH", "name": "Package width", "tags": {}},
                {"id": "PACKAGE_HEIGHT", "name": "Package height", "tags": {}},
                {"id": "SIZE", "name": "Size", "tags": {}},
            ],
        }
        db.commit()

    response = client.get("/api/drafts/1/attribute-suggestions?category_id=MLM123")

    assert response.status_code == 200
    suggestions = {
        item["attribute_id"]: item["value_name"] for item in response.json()["suggestions"]
    }
    assert suggestions == {
        "WEIGHT": "1.2 pounds",
        "PACKAGE_LENGTH": "30 cm",
        "PACKAGE_WIDTH": "20 cm",
        "PACKAGE_HEIGHT": "10 cm",
    }
    assert "SIZE" not in suggestions


def test_other_source_variant_does_not_inherit_selected_page_measurements():
    client, testing_session = make_client()
    with testing_session() as db:
        source = SourceProduct(
            source_url="https://amazon.com/dp/B000TEST01",
            asin="B000TEST01",
            raw_status=SourceProductStatus.COLLECTED,
            variants_json=[
                {"asin": "B000TEST01", "attributes": {}, "selected": True},
                {"asin": "B000TEST02", "attributes": {}, "selected": False},
            ],
            measurements_json={
                "item_weight": {"value": 1.2, "unit": "lb", "raw": "1.2 pounds"},
            },
        )
        db.add(source)
        db.flush()
        draft = db.get(ProductDraft, 1)
        draft.source_product_id = source.id
        draft.source_variant_asin = "B000TEST02"
        cache = db.query(MeliMetadataCache).one()
        cache.payload_json = {
            "verified": True,
            "attributes": [{"id": "WEIGHT", "name": "Weight", "tags": {}}],
        }
        db.commit()

    response = client.get("/api/drafts/1/attribute-suggestions?category_id=MLM123")

    assert response.status_code == 200
    assert response.json()["suggestions"] == []


def test_legacy_selected_marker_and_empty_draft_asin_cannot_authorize_measurements():
    client, testing_session = make_client()
    with testing_session() as db:
        source = SourceProduct(
            source_url="https://amazon.com/dp/B000TEST01",
            asin="B000TEST01",
            raw_status=SourceProductStatus.COLLECTED,
            variants_json=[
                {"asin": "B000TEST02", "attributes": {}, "selected": True},
            ],
            measurements_json={
                "item_weight": {"value": 1.2, "unit": "lb", "raw": "1.2 pounds"},
            },
        )
        db.add(source)
        db.flush()
        draft = db.get(ProductDraft, 1)
        draft.source_product_id = source.id
        draft.source_variant_asin = ""
        cache = db.query(MeliMetadataCache).one()
        cache.payload_json = {
            "verified": True,
            "attributes": [{"id": "WEIGHT", "name": "Weight", "tags": {}}],
        }
        db.commit()

    response = client.get("/api/drafts/1/attribute-suggestions?category_id=MLM123")

    assert response.status_code == 200
    assert response.json()["suggestions"] == []


def test_legacy_duplicate_attributes_can_be_read_but_not_built():
    client, testing_session = make_client()
    with testing_session() as db:
        db.add(
            DraftListingConfig(
                product_draft_id=1,
                store_id=1,
                site_id="MLM",
                category_id="MLM123",
                listing_type_id="gold_special",
                fulfillment="not_full",
                shipping_mode="me2",
                shipping_logistic_type="drop_off",
                attributes_json=[
                    {"id": "BRAND", "value_name": "Acme"},
                    {"id": "brand", "value_name": "Other"},
                ],
            )
        )
        db.commit()

    readable = client.get("/api/drafts/1/listing-config")
    review = client.post(
        "/api/reviews/local?product_draft_id=1",
        json={
            "title": "Bottle",
            "target_site_id": "MLM",
            "target_category_id": "MLM123",
            "price": 9.99,
            "currency": "MXN",
            "stock": 2,
            "image_urls": ["https://example.com/a.jpg"],
        },
    )

    assert readable.status_code == 200
    assert len(readable.json()["attributes"]) == 2
    assert review.status_code == 409
    assert review.json()["detail"] == {
        "code": "listing_config_stale",
        "errors": ["category_attribute_duplicate:BRAND"],
    }


def test_listing_config_preserves_value_ids_and_rejects_duplicate_attributes():
    client, _ = make_client()
    payload = config_payload() | {
        "attributes": [
            {"id": "COLOR", "value_id": "52028", "value_name": "Blue"},
        ]
    }

    saved = client.put("/api/drafts/1/listing-config", json=payload)
    duplicate = client.put(
        "/api/drafts/1/listing-config",
        json=payload
        | {
            "attributes": [
                {"id": "COLOR", "value_name": "Blue"},
                {"id": "color", "value_name": "Red"},
            ]
        },
    )

    assert saved.status_code == 200
    assert saved.json()["attributes"] == [
        {"id": "COLOR", "value_name": "Blue", "value_id": "52028"}
    ]
    assert duplicate.status_code == 422
    assert "attribute IDs must be unique" in duplicate.text


def test_listing_config_rejects_missing_required_cached_category_attribute():
    client, testing_session = make_client()
    with testing_session() as db:
        cache = db.query(MeliMetadataCache).one()
        cache.payload_json = {
                    "verified": True,
                    "attributes": [
                        {"id": "BRAND", "tags": {"required": True}},
                        {"id": "COLOR", "tags": {"catalog_required": True}},
                        {"id": "MODEL", "tags": {}},
                    ],
                }
        db.commit()

    response = client.put("/api/drafts/1/listing-config", json=config_payload())

    assert response.status_code == 422
    assert response.json()["detail"] == {
        "code": "invalid_category_attributes",
        "errors": ["required_category_attribute_missing:COLOR"],
    }


def test_existing_listing_config_update_persists_new_shipping_selection():
    client, testing_session = make_client()
    client.put("/api/drafts/1/listing-config", json=config_payload())

    response = client.put(
        "/api/drafts/1/listing-config",
        json=config_payload() | {"shipping_logistic_type": "self_service"},
    )

    assert response.status_code == 200
    assert response.json()["shipping_logistic_type"] == "self_service"
    assert client.get("/api/drafts/1/listing-config").json()[
        "shipping_logistic_type"
    ] == "self_service"
    with testing_session() as db:
        latest = db.query(AuditEvent).order_by(AuditEvent.id.desc()).first()
        assert latest.action == "draft_listing_config_updated"
        assert latest.before_json["shipping_logistic_type"] == "drop_off"
        assert latest.after_json["shipping_logistic_type"] == "self_service"


def test_listing_config_rolls_back_when_audit_write_fails(monkeypatch):
    client, testing_session = make_client()

    def fail_audit(*args, **kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(draft_listing_configs, "create_audit_event", fail_audit)
    with pytest.raises(RuntimeError, match="audit unavailable"):
        client.put("/api/drafts/1/listing-config", json=config_payload())

    with testing_session() as db:
        draft = db.get(ProductDraft, 1)
        assert draft.target_category_id == ""
        assert draft.content_version == 1
        assert db.query(DraftListingConfig).count() == 0
        assert db.query(AuditEvent).count() == 0


def test_listing_config_rejects_full_fulfillment():
    client, _ = make_client()
    payload = config_payload() | {"fulfillment": " FULL "}

    response = client.put("/api/drafts/1/listing-config", json=payload)

    assert response.status_code == 422
    assert "FULL fulfillment is excluded" in response.text


def test_listing_config_rejects_full_or_incomplete_shipping_selection():
    client, _ = make_client()

    full = client.put(
        "/api/drafts/1/listing-config",
        json=config_payload() | {"shipping_logistic_type": "fulfillment"},
    )
    incomplete = client.put(
        "/api/drafts/1/listing-config",
        json=config_payload() | {"shipping_logistic_type": ""},
    )

    assert full.status_code == 422
    assert "FULL fulfillment is excluded" in full.text
    assert incomplete.status_code == 422
    assert "must be selected together" in incomplete.text


def test_missing_listing_config_can_be_read_as_optional():
    client, _ = make_client()

    response = client.get("/api/drafts/1/listing-config?optional=true")

    assert response.status_code == 200
    assert response.json() is None


def test_publish_preview_from_saved_draft_config(monkeypatch):
    def current_shipping(*args, **kwargs):
        return []

    monkeypatch.setattr(
        "app.api.routes.publishing._validate_current_store_shipping",
        current_shipping,
    )
    client, testing_session = make_client()
    client.put("/api/drafts/1/listing-config", json=config_payload())
    review_result_id = seed_publish_review(testing_session)
    client.post("/api/drafts/1/approval", json={"approved_by": "operator"})

    response = client.post(
        "/api/publishing/preview-from-draft",
        json={
            "product_draft_id": 1,
            "review": review_payload() | {"review_result_id": review_result_id},
            "valid_listing_type_ids": ["gold_special"],
            "human_approved": True,
        },
    )

    assert response.status_code == 200
    assert response.json() == {"allowed": True, "errors": []}


def test_publish_preview_from_saved_config_requires_existing_config():
    client, _ = make_client()

    response = client.post(
        "/api/publishing/preview-from-draft",
        json={
            "product_draft_id": 1,
            "review": review_payload(),
            "valid_listing_type_ids": ["gold_special"],
            "human_approved": True,
        },
    )

    assert response.status_code == 404
    assert "Listing config not found" in response.text


def test_publish_preview_blocks_missing_required_category_attribute():
    client, testing_session = make_client()
    client.put("/api/drafts/1/listing-config", json=config_payload())
    review_result_id = seed_publish_review(testing_session)
    client.post("/api/drafts/1/approval", json={"approved_by": "operator"})
    with testing_session() as db:
        cache = db.query(MeliMetadataCache).one()
        cache.payload_json = {
                    "verified": True,
                        "attributes": [
                            {"id": "BRAND", "tags": {"required": True}},
                            {"id": "MODEL", "tags": {}},
                            {"id": "GTIN", "tags": {"required": True}},
                    ],
                }
        db.commit()

    response = client.post(
        "/api/publishing/preview-from-draft",
        json={
            "product_draft_id": 1,
            "review": review_payload() | {"review_result_id": review_result_id},
            "valid_listing_type_ids": ["gold_special"],
            "human_approved": True,
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == {
        "code": "listing_config_stale",
        "errors": ["required_category_attribute_missing:GTIN"],
    }
