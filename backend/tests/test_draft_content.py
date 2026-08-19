from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.audit_event import AuditEvent
from app.models.product_draft import ProductDraft
from app.models.product_draft_approval import ProductDraftApproval
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

    def override_get_db():
        with testing_session() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app), testing_session


def teardown_function():
    app.dependency_overrides.clear()


def seed_reviewed_draft(testing_session) -> None:
    with testing_session() as db:
        draft = ProductDraft(
            title="Original bottle",
            description="Original description",
            brand="Unbranded",
            source_price=9.99,
            source_currency="USD",
            image_urls_json=["https://example.com/original.jpg"],
            risk_status="low",
        )
        db.add(draft)
        db.flush()
        review = ReviewResult(
            product_draft_id=draft.id,
            provider="behavioral_aggregate",
            model="claude+nvidia",
            prompt_version="meli-behavioral-audit-v4",
            provider_status="completed",
            risk_level="low",
            decision=ReviewDecision.PASS,
            reasons_json={"reason_codes": [], "reasons": []},
            suggested_changes_json={"suggested_changes": []},
            draft_version=1,
        )
        db.add(review)
        db.flush()
        db.add(
            ProductDraftApproval(
                product_draft_id=draft.id,
                review_result_id=review.id,
                status="approved",
                approved_by="operator",
                draft_version=1,
            )
        )
        db.commit()


def test_draft_content_update_versions_and_invalidates_old_review():
    client, testing_session = make_client()
    seed_reviewed_draft(testing_session)

    response = client.put(
        "/api/drafts/1/content",
        json={
            "expected_content_version": 1,
            "title": "  Updated   bottle  ",
            "description": "\nUpdated description\n",
            "brand": " Updated   brand ",
            "image_urls": [
                "https://example.com/new.jpg",
                "https://example.com/new.jpg",
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Updated bottle"
    assert body["description"] == "Updated description"
    assert body["brand"] == "Unbranded"
    assert body["image_urls"] == ["https://example.com/new.jpg"]
    assert body["content_version"] == 2
    assert body["risk_status"] == "unreviewed"
    assert body["source_price"] == 9.99
    assert body["source_currency"] == "USD"
    assert client.get("/api/drafts/1").json() == body
    assert client.get("/api/reviews/drafts/1/latest-behavioral").json() is None

    with testing_session() as db:
        draft = db.get(ProductDraft, 1)
        approval = db.query(ProductDraftApproval).one()
        event = db.query(AuditEvent).filter(AuditEvent.action == "draft.content_updated").one()
        assert draft.content_version == 2
        assert approval.draft_version == 1
        assert event.before_json["content_version"] == 1
        assert event.after_json["content_version"] == 2
        assert event.after_json["changed_fields"] == [
            "title",
            "description",
            "image_urls_json",
        ]


def test_draft_content_update_rejects_stale_version_and_noop_does_not_increment():
    client, testing_session = make_client()
    seed_reviewed_draft(testing_session)
    payload = {
        "expected_content_version": 1,
        "title": "Original bottle",
        "description": "Original description",
        "brand": "Unbranded",
        "image_urls": ["https://example.com/original.jpg"],
    }

    noop = client.put("/api/drafts/1/content", json=payload)
    assert noop.status_code == 200
    assert noop.json()["content_version"] == 1

    changed = client.put(
        "/api/drafts/1/content",
        json={**payload, "title": "First writer"},
    )
    assert changed.status_code == 200
    assert changed.json()["content_version"] == 2

    stale = client.put(
        "/api/drafts/1/content",
        json={**payload, "title": "Stale writer"},
    )
    assert stale.status_code == 409
    assert stale.json()["detail"] == "draft_content_version_conflict"

    with testing_session() as db:
        draft = db.get(ProductDraft, 1)
        assert draft.title == "First writer"
        assert draft.content_version == 2
        assert db.query(AuditEvent).filter(AuditEvent.action == "draft.content_updated").count() == 1


def test_draft_content_update_validates_title_images_and_missing_draft():
    client, testing_session = make_client()
    seed_reviewed_draft(testing_session)
    base = {
        "expected_content_version": 1,
        "title": "Valid title",
        "description": "",
        "brand": "",
        "image_urls": [],
    }

    assert client.put("/api/drafts/1/content", json={**base, "title": "   "}).status_code == 422
    assert client.put(
        "/api/drafts/1/content",
        json={**base, "image_urls": ["javascript:alert(1)"]},
    ).status_code == 422
    assert client.put("/api/drafts/999/content", json=base).status_code == 404
    assert client.get("/api/drafts/999").status_code == 404
