from fastapi.testclient import TestClient
import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import imports
from app.api.routes.imports import AmazonUrlImport, create_amazon_url_collection_job
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
        json={"source_url": "https://www.amazon.com/dp/B000TEST01", "target_site_id": "MLM"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "pending"
    list_response = client.get("/api/imports/amazon-url/jobs")
    assert list_response.status_code == 200
    assert list_response.json()[0]["source_url"] == "https://amazon.com/dp/B000TEST01"
    with testing_session() as db:
        job = db.query(CollectionJob).one()
        assert job.status == CollectionJobStatus.PENDING


def test_single_amazon_url_job_creation_reuses_existing_normalized_job():
    client, testing_session = make_client()

    first = client.post(
        "/api/imports/amazon-url/jobs",
        json={
            "source_url": "https://www.amazon.com/dp/B000TEST01?tag=first",
            "target_site_id": "mlm",
        },
    )
    second = client.post(
        "/api/imports/amazon-url/jobs",
        json={
            "source_url": "https://m.amazon.com/gp/product/B000TEST01/ref=second",
            "target_site_id": "MLM",
        },
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    with testing_session() as db:
        job = db.query(CollectionJob).one()
        assert job.source_identity == "https://amazon.com/dp/B000TEST01"


def test_amazon_url_batch_normalizes_deduplicates_and_reports_invalid_rows():
    client, testing_session = make_client()

    response = client.post(
        "/api/imports/amazon-url/jobs/batch",
        json={
            "source_urls": [
                "https://www.amazon.com/dp/B000TEST01?tag=affiliate-20",
                "https://m.amazon.com/gp/product/B000TEST01/ref=something",
                "https://www.amazon.ca/dp/B000TEST02",
                "https://example.com/not-amazon",
            ],
            "target_site_id": "MLM",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["created_count"] == 2
    assert body["duplicate_count"] == 1
    assert body["existing_count"] == 0
    assert body["invalid_count"] == 1
    assert [item["outcome"] for item in body["items"]] == [
        "created",
        "duplicate_input",
        "created",
        "invalid",
    ]
    with testing_session() as db:
        assert [job.source_url for job in db.query(CollectionJob).order_by(CollectionJob.id)] == [
            "https://amazon.com/dp/B000TEST01",
            "https://amazon.ca/dp/B000TEST02",
        ]


def test_amazon_url_batch_skips_existing_unless_operator_allows_recollection():
    client, testing_session = make_client()
    payload = {
        "source_urls": ["https://www.amazon.com/dp/B000TEST01"],
        "target_site_id": "MLM",
    }

    first = client.post("/api/imports/amazon-url/jobs/batch", json=payload)
    second = client.post("/api/imports/amazon-url/jobs/batch", json=payload)
    forced = client.post(
        "/api/imports/amazon-url/jobs/batch",
        json={**payload, "allow_existing": True},
    )

    assert first.json()["created_count"] == 1
    assert second.json()["existing_count"] == 1
    assert second.json()["items"][0]["job"]["id"] == first.json()["items"][0]["job"]["id"]
    assert forced.json()["created_count"] == 1
    with testing_session() as db:
        assert db.query(CollectionJob).count() == 2


def test_amazon_url_job_creation_rejects_invalid_url_site_and_oversized_batch():
    client, testing_session = make_client()

    invalid_url = client.post(
        "/api/imports/amazon-url/jobs",
        json={"source_url": "https://example.com/item", "target_site_id": "MLM"},
    )
    invalid_site = client.post(
        "/api/imports/amazon-url/jobs/batch",
        json={
            "source_urls": ["https://www.amazon.com/dp/B000TEST01"],
            "target_site_id": "XXX",
        },
    )
    oversized = client.post(
        "/api/imports/amazon-url/jobs/batch",
        json={
            "source_urls": [
                f"https://www.amazon.com/dp/B{i:09d}" for i in range(101)
            ],
            "target_site_id": "MLM",
        },
    )
    oversized_url = client.post(
        "/api/imports/amazon-url/jobs/batch",
        json={
            "source_urls": [f"https://www.amazon.com/dp/B000TEST01?x={'a' * 2048}"],
            "target_site_id": "MLM",
        },
    )

    assert invalid_url.status_code == 422
    assert invalid_url.json()["detail"] == "only_public_amazon_product_urls_allowed"
    assert invalid_site.status_code == 422
    assert invalid_site.json()["detail"] == "unsupported_mercado_libre_site"
    assert oversized.status_code == 422
    assert oversized_url.status_code == 422
    with testing_session() as db:
        assert db.query(CollectionJob).count() == 0


def test_sqlite_file_requests_reuse_one_collection_job(tmp_path):
    database_path = tmp_path / "collection-concurrency.db"
    engine = create_engine(
        f"sqlite:///{database_path}",
        connect_args={"check_same_thread": False, "timeout": 10},
    )
    import_all_models()
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    both_requests_ready = Barrier(2)

    def create_job():
        with testing_session() as db:
            both_requests_ready.wait(timeout=10)
            return create_amazon_url_collection_job(
                AmazonUrlImport(
                    source_url="https://www.amazon.com/dp/B000TEST01",
                    target_site_id="MLM",
                ),
                db,
            ).id

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            job_ids = list(pool.map(lambda _: create_job(), range(2)))
        assert job_ids[0] == job_ids[1]
        with testing_session() as db:
            assert db.query(CollectionJob).count() == 1
    finally:
        engine.dispose()


def test_amazon_url_identity_keeps_domains_and_asins_distinct():
    client, testing_session = make_client()

    response = client.post(
        "/api/imports/amazon-url/jobs/batch",
        json={
            "source_urls": [
                "https://www.amazon.com/gp/aw/d/b000test01",
                "https://www.amazon.ca/dp/B000TEST01",
                "https://www.amazon.com/dp/B000TEST02",
            ],
            "target_site_id": "MLM",
        },
    )

    assert response.status_code == 200
    assert response.json()["created_count"] == 3
    with testing_session() as db:
        assert {job.source_url for job in db.query(CollectionJob)} == {
            "https://amazon.com/dp/B000TEST01",
            "https://amazon.ca/dp/B000TEST01",
            "https://amazon.com/dp/B000TEST02",
        }


def test_legacy_lowercase_site_job_is_reused():
    client, testing_session = make_client()
    with testing_session() as db:
        db.add(
            CollectionJob(
                source_url="https://www.amazon.com/dp/B000TEST01?tag=legacy",
                source_identity=None,
                target_site_id="mlm",
            )
        )
        db.commit()

    response = client.post(
        "/api/imports/amazon-url/jobs",
        json={"source_url": "https://amazon.com/dp/B000TEST01", "target_site_id": "MLM"},
    )

    assert response.status_code == 200
    with testing_session() as db:
        assert db.query(CollectionJob).count() == 1


def test_collection_job_list_is_bounded_and_supports_offset():
    client, testing_session = make_client()
    with testing_session() as db:
        db.add_all(
            [
                CollectionJob(
                    source_url=f"https://amazon.com/dp/B{i:09d}",
                    source_identity=f"https://amazon.com/dp/B{i:09d}",
                    target_site_id="MLM",
                )
                for i in range(105)
            ]
        )
        db.commit()

    first_page = client.get("/api/imports/amazon-url/jobs")
    last_page = client.get("/api/imports/amazon-url/jobs?limit=5&offset=100")

    assert first_page.status_code == 200
    assert len(first_page.json()) == 100
    assert len(last_page.json()) == 5
    assert first_page.json()[0]["id"] > last_page.json()[0]["id"]


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
        json={"source_url": "https://www.amazon.com/dp/B000TEST01", "target_site_id": "MLM"},
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
        json={"source_url": "https://www.amazon.com/dp/B000TEST01", "target_site_id": "MLM"},
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


def test_collection_job_records_unexpected_collector_failure(monkeypatch):
    async def fake_collect(source_url: str, target_site_id: str):
        raise RuntimeError("browser process exited")

    monkeypatch.setattr(imports, "collect_amazon_page", fake_collect)
    client, testing_session = make_client()
    create_response = client.post(
        "/api/imports/amazon-url/jobs",
        json={"source_url": "https://www.amazon.com/dp/B000TEST01", "target_site_id": "MLM"},
    )

    response = client.post(f"/api/imports/amazon-url/jobs/{create_response.json()['id']}/run")

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert "browser process exited" in response.json()["message"]
    with testing_session() as db:
        job = db.query(CollectionJob).one()
        source = db.query(SourceProduct).one()
        assert job.status == CollectionJobStatus.FAILED
        assert job.completed_at is not None
        assert source.raw_status == SourceProductStatus.FAILED


def test_completed_collection_job_is_idempotent(monkeypatch):
    calls = 0

    async def fake_collect(source_url: str, target_site_id: str):
        nonlocal calls
        calls += 1
        return CollectionResult(
            status=CollectionStatus.COLLECTED,
            source_url=source_url,
            message="collected",
            draft=ProductDraftCreate(
                title="One Draft",
                target_site_id=target_site_id,
                price=10,
                currency="USD",
                stock=1,
                image_urls=[],
            ),
        )

    monkeypatch.setattr(imports, "collect_amazon_page", fake_collect)
    client, testing_session = make_client()
    create_response = client.post(
        "/api/imports/amazon-url/jobs",
        json={"source_url": "https://www.amazon.com/dp/B000TEST01", "target_site_id": "MLM"},
    )
    run_url = f"/api/imports/amazon-url/jobs/{create_response.json()['id']}/run"

    first = client.post(run_url)
    second = client.post(run_url)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["draft_id"] == first.json()["draft_id"]
    assert calls == 1
    with testing_session() as db:
        assert db.query(ProductDraft).count() == 1
        assert db.query(SourceProduct).count() == 1


def test_collection_job_timeout_is_persisted_as_safe_failure(monkeypatch):
    async def slow_collect(source_url: str, target_site_id: str):
        await asyncio.sleep(1)

    monkeypatch.setattr(imports, "collect_amazon_page", slow_collect)
    monkeypatch.setattr(imports.settings, "job_execution_timeout_seconds", 0.01)
    client, testing_session = make_client()
    create_response = client.post(
        "/api/imports/amazon-url/jobs",
        json={"source_url": "https://www.amazon.com/dp/B000TEST01", "target_site_id": "MLM"},
    )

    response = client.post(f"/api/imports/amazon-url/jobs/{create_response.json()['id']}/run")

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert response.json()["message"] == "Collection timed out; retry is safe."
    with testing_session() as db:
        assert db.query(CollectionJob).one().status == CollectionJobStatus.FAILED
