from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.product_draft import ProductDraft
from app.models.meli_metadata_cache import MeliMetadataCache
from app.models.registry import import_all_models
from app.models.review_result import ReviewDecision, ReviewResult


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
            ProductDraft(
                title="Bottle",
                description="Leak proof.",
                target_site_id="MLM",
                target_category_id="",
                price=9.99,
                currency="MXN",
                stock=2,
                image_urls_json=["https://example.com/a.jpg"],
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
        "category_id": "MLM123",
        "listing_type_id": "gold_special",
        "fulfillment": "not_full",
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
    assert body["category_id"] == "MLM123"
    assert body["listing_type_id"] == "gold_special"
    assert body["attributes"][0]["id"] == "BRAND"

    get_response = client.get("/api/drafts/1/listing-config")
    assert get_response.status_code == 200
    assert get_response.json()["attributes"][1]["value_name"] == "B-100"

    with testing_session() as db:
        draft = db.get(ProductDraft, 1)
        assert draft.target_category_id == "MLM123"
        assert draft.listing_type_id == "gold_special"


def test_listing_config_rejects_full_fulfillment():
    client, _ = make_client()
    payload = config_payload() | {"fulfillment": " FULL "}

    response = client.put("/api/drafts/1/listing-config", json=payload)

    assert response.status_code == 422
    assert "FULL fulfillment is excluded" in response.text


def test_missing_listing_config_can_be_read_as_optional():
    client, _ = make_client()

    response = client.get("/api/drafts/1/listing-config?optional=true")

    assert response.status_code == 200
    assert response.json() is None


def test_publish_preview_from_saved_draft_config():
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
        db.add(
            MeliMetadataCache(
                cache_key="category_attributes:MLM123",
                payload_json={
                    "attributes": [
                        {"id": "BRAND", "tags": {"required": True}},
                        {"id": "GTIN", "tags": {"required": True}},
                    ]
                },
            )
        )
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

    assert response.status_code == 200
    assert response.json() == {
        "allowed": False,
        "errors": ["required_category_attribute_missing:GTIN"],
    }
