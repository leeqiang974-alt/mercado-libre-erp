from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import drafts
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.audit_event import AuditEvent
from app.models.registry import import_all_models


def test_failed_manual_ai_request_is_audited_without_provider_details(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    import_all_models()
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_db():
        with testing_session() as db:
            yield db

    async def provider_unavailable(*_args, **_kwargs):
        raise HTTPException(status_code=503, detail={"code": "deepseek_api_key_required"})

    app.dependency_overrides[get_db] = override_db
    monkeypatch.setattr(drafts, "generate_and_save_draft_content", provider_unavailable)
    try:
        response = TestClient(app).post(
            "/api/drafts/77/generate-content",
            json={"category_id": "CBT414091", "fields": ["description"]},
        )
        assert response.status_code == 503
        with testing_session() as db:
            event = db.query(AuditEvent).one()
        assert event.action == "draft.ai_content_failed"
        assert event.entity_id == "77"
        assert event.after_json == {
            "status_code": 503,
            "code": "deepseek_api_key_required",
            "requested_fields": ["description"],
        }
    finally:
        app.dependency_overrides.clear()
