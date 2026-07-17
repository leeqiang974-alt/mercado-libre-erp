from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import reviews
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.product_draft import ProductDraft
from app.models.draft_listing_config import DraftListingConfig
from app.models.registry import import_all_models
from app.models.review_result import ReviewResult
from app.models.audit_event import AuditEvent
from app.schemas.reviews import ReviewResponse


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
        draft = ProductDraft(
                title="Bottle",
                target_site_id="MLM",
                target_category_id="MLM123",
                price=9.99,
                currency="USD",
                stock=1,
                image_urls_json=["https://example.com/a.jpg"],
            )
        db.add(draft)
        db.flush()
        db.add(
            DraftListingConfig(
                product_draft_id=draft.id,
                site_id="MLM",
                category_id="MLM123",
                listing_type_id="gold_special",
                fulfillment="not_full",
                attributes_json=[],
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


def draft_payload():
    return {
        "title": "Bottle",
        "description": "Leak proof.",
        "target_site_id": "MLM",
        "price": 9.99,
        "currency": "USD",
        "stock": 1,
        "image_urls": ["https://example.com/a.jpg"],
    }


def test_local_review_can_persist_result_for_draft():
    client, testing_session = make_client()

    response = client.post("/api/reviews/local?product_draft_id=1", json=draft_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "local_policy"
    assert body["review_result_id"] == 1
    with testing_session() as db:
        row = db.query(ReviewResult).one()
        assert row.product_draft_id == 1
        assert row.provider == "local_policy"
        assert row.decision.value == "pass"


def test_review_history_can_be_listed_for_draft():
    client, _ = make_client()
    client.post("/api/reviews/local?product_draft_id=1", json=draft_payload())

    response = client.get("/api/reviews/drafts/1")

    assert response.status_code == 200
    body = response.json()
    assert body[0]["id"] == 1
    assert body[0]["provider"] == "local_policy"
    assert body[0]["decision"] == "pass"


def test_claude_review_can_persist_result_for_draft(monkeypatch):
    class FakeClaudeClient:
        def __init__(self, api_key: str, model: str = ""):
            pass

        async def review_draft(self, draft):
            return ReviewResponse(
                provider="claude",
                decision="needs_human_review",
                risk_level="medium",
                reason_codes=["brand_risk"],
                reasons=["verify"],
            )

    monkeypatch.setattr(reviews, "ClaudeReviewClient", FakeClaudeClient)
    client, testing_session = make_client()

    response = client.post("/api/reviews/claude?product_draft_id=1", json=draft_payload())

    assert response.status_code == 200
    assert response.json()["review_result_id"] == 1
    with testing_session() as db:
        row = db.query(ReviewResult).one()
        assert row.provider == "claude"
        assert row.decision.value == "needs_human_review"


def test_nvidia_review_can_persist_result_for_draft(monkeypatch):
    class FakeNvidiaClient:
        def __init__(self, api_key: str, model: str = ""):
            pass

        async def pre_screen_draft(self, draft):
            return ReviewResponse(
                provider="nvidia",
                decision="block",
                risk_level="high",
                reason_codes=["restricted_item"],
                reasons=["blocked"],
            )

    monkeypatch.setattr(reviews, "NvidiaReviewClient", FakeNvidiaClient)
    client, testing_session = make_client()

    response = client.post("/api/reviews/nvidia?product_draft_id=1", json=draft_payload())

    assert response.status_code == 200
    assert response.json()["review_result_id"] == 1
    with testing_session() as db:
        row = db.query(ReviewResult).one()
        assert row.provider == "nvidia"
        assert row.decision.value == "block"


def test_behavioral_audit_persists_both_provider_results_and_orchestration_audit(monkeypatch):
    class FakeClaudeClient:
        model = "claude-test"

        def __init__(self, api_key: str, model: str = ""):
            pass

        async def review_draft(self, draft):
            return ReviewResponse(
                provider="claude",
                decision="pass",
                risk_level="low",
                reason_codes=[],
                reasons=[],
            )

    class FakeNvidiaClient:
        model = "nvidia-test"

        def __init__(self, api_key: str, model: str = ""):
            pass

        async def pre_screen_draft(self, draft):
            return ReviewResponse(
                provider="nvidia",
                decision="needs_human_review",
                risk_level="medium",
                reason_codes=["verify"],
                reasons=["verify"],
            )

    monkeypatch.setattr(reviews, "ClaudeReviewClient", FakeClaudeClient)
    monkeypatch.setattr(reviews, "NvidiaReviewClient", FakeNvidiaClient)
    client, testing_session = make_client()

    response = client.post(
        "/api/reviews/behavioral-audit?product_draft_id=1",
        json=draft_payload(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["aggregate"]["decision"] == "needs_human_review"
    assert {body["nvidia"]["review_result_id"], body["claude"]["review_result_id"]} == {1, 2}
    with testing_session() as db:
        rows = db.query(ReviewResult).order_by(ReviewResult.id).all()
        assert [(row.provider, row.model) for row in rows] == [
            ("nvidia", "nvidia-test"),
            ("claude", "claude-test"),
            ("claude+nvidia_behavioral_audit", "nvidia-test+claude-test"),
        ]
        assert body["aggregate"]["review_result_id"] == 3
        audit = db.query(AuditEvent).filter(AuditEvent.action == "review.behavioral_audit.completed").one()
        assert audit.actor_id == "claude+nvidia"
