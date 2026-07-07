from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import imports
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.collection_job import CollectionJob, CollectionJobStatus
from app.models.product_draft import ProductDraft
from app.models.registry import import_all_models
from app.models.source_product import SourceProduct, SourceProductStatus
from app.schemas.drafts import ProductDraftCreate
from app.services.amazon.collector import CollectionResult, CollectionStatus


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


def test_amazon_url_collection_job_can_be_created_and_listed():
    client, testing_session = make_client()

    response = client.post(
        "/api/imports/amazon-url/jobs",
        json={"source_url": "https://www.amazon.com/dp/B000TEST", "target_site_id": "MLM"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "pending"
    list_response = client.get("/api/imports/amazon-url/jobs")
    assert list_response.status_code == 200
    assert list_response.json()[0]["source_url"] == "https://www.amazon.com/dp/B000TEST"
    with testing_session() as db:
        job = db.query(CollectionJob).one()
        assert job.status == CollectionJobStatus.PENDING


def test_running_collection_job_persists_source_and_draft(monkeypatch):
    async def fake_collect(source_url: str, target_site_id: str):
        return CollectionResult(
            status=CollectionStatus.COLLECTED,
            source_url=source_url,
            message="collected",
            draft=ProductDraftCreate(
                title="Queued Bottle",
                target_site_id=target_site_id,
                price=12.5,
                currency="USD",
                stock=3,
                image_urls=["https://example.com/a.jpg"],
            ),
        )

    monkeypatch.setattr(imports, "collect_amazon_page", fake_collect)
    client, testing_session = make_client()
    create_response = client.post(
        "/api/imports/amazon-url/jobs",
        json={"source_url": "https://www.amazon.com/dp/B000TEST", "target_site_id": "MLM"},
    )

    response = client.post(f"/api/imports/amazon-url/jobs/{create_response.json()['id']}/run")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["source_product_id"] == 1
    assert body["draft_id"] == 1
    with testing_session() as db:
        assert db.query(SourceProduct).one().raw_status == SourceProductStatus.COLLECTED
        assert db.query(ProductDraft).one().title == "Queued Bottle"
        assert db.query(CollectionJob).one().status == CollectionJobStatus.COMPLETED


def test_running_collection_job_records_manual_action(monkeypatch):
    async def fake_collect(source_url: str, target_site_id: str):
        return CollectionResult(
            status=CollectionStatus.NEEDS_MANUAL_ACTION,
            source_url=source_url,
            message="Amazon challenge detected; manual action required.",
            draft=None,
        )

    monkeypatch.setattr(imports, "collect_amazon_page", fake_collect)
    client, testing_session = make_client()
    create_response = client.post(
        "/api/imports/amazon-url/jobs",
        json={"source_url": "https://www.amazon.com/dp/B000TEST", "target_site_id": "MLM"},
    )

    response = client.post(f"/api/imports/amazon-url/jobs/{create_response.json()['id']}/run")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "needs_manual_action"
    assert body["draft_id"] is None
    with testing_session() as db:
        source = db.query(SourceProduct).one()
        assert source.raw_status == SourceProductStatus.NEEDS_MANUAL_ACTION
        assert "manual action" in source.collection_error
        assert db.query(ProductDraft).count() == 0
