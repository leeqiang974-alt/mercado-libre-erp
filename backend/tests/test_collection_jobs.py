from fastapi.testclient import TestClient
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
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
from app.models.audit_event import AuditEvent
from app.models.amazon_domain_throttle import AmazonDomainThrottle
from app.models.product_draft import ProductDraft
from app.models.keyword_collection_campaign import KeywordCollectionCampaign
from app.models.registry import import_all_models
from app.models.source_product import SourceProduct, SourceProductStatus
from app.schemas.drafts import ProductDraftCreate
from app.schemas.source_products import AmazonSourceSnapshot
from app.services.amazon.collector import CollectionResult, CollectionStatus
from app.services import collection_jobs as collection_jobs_service


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


def test_collection_job_schedule_is_serialized_with_utc_offset():
    client, testing_session = make_client()
    with testing_session() as db:
        db.add(
            CollectionJob(
                source_url="https://amazon.com/dp/B000TEST01",
                target_site_id="MLM",
                next_attempt_at=datetime.now(UTC) + timedelta(minutes=5),
            )
        )
        db.commit()

    response = client.get("/api/imports/amazon-url/jobs")

    assert response.status_code == 200
    next_attempt_at = response.json()[0]["next_attempt_at"]
    assert next_attempt_at.endswith("Z") or next_attempt_at.endswith("+00:00")


def test_source_variant_collection_job_preserves_domain_and_reuses_existing_job():
    client, testing_session = make_client()
    with testing_session() as db:
        source = SourceProduct(
            source_url="https://www.amazon.com.mx/dp/B000TEST01",
            asin="B000TEST01",
            raw_status=SourceProductStatus.COLLECTED,
            variants_json=[
                {"asin": "B000TEST01", "attributes": {"Color": "Black"}},
                {"asin": "B000TEST02", "attributes": {"Color": "Blue"}},
            ],
        )
        db.add(source)
        db.commit()
        source_id = source.id

    first = client.post(
        f"/api/imports/source-products/{source_id}/variants/B000TEST02/collection-job",
        json={"target_site_id": "MLB", "collector_kind": "browser_extension"},
    )
    repeated = client.post(
        f"/api/imports/source-products/{source_id}/variants/b000test02/collection-job",
        json={"target_site_id": "MLB"},
    )

    assert first.status_code == 200
    assert first.json()["source_url"] == "https://amazon.com.mx/dp/B000TEST02"
    assert first.json()["target_site_id"] == "MLB"
    assert first.json()["status"] == "pending"
    assert first.json()["collector_kind"] == "browser_extension"
    assert repeated.status_code == 200
    assert repeated.json()["id"] == first.json()["id"]
    with testing_session() as db:
        assert db.query(CollectionJob).count() == 1
        assert db.query(CollectionJob).one().collector_kind == "browser_extension"


def test_source_variant_collection_job_reuses_exact_draft_without_prior_job():
    client, testing_session = make_client()
    with testing_session() as db:
        parent = SourceProduct(
            source_url="https://www.amazon.com/dp/B000TEST01",
            asin="B000TEST01",
            raw_status=SourceProductStatus.COLLECTED,
            variants_json=[
                {"asin": "B000TEST01", "attributes": {"Size": "1 ML"}},
                {"asin": "B000TEST02", "attributes": {"Size": "2.5 ML"}},
            ],
        )
        exact_source = SourceProduct(
            source_url="https://amazon.com/dp/B000TEST02",
            asin="B000TEST02",
            raw_status=SourceProductStatus.COLLECTED,
            collection_method="browser_extension",
        )
        db.add_all([parent, exact_source])
        db.flush()
        exact_draft = ProductDraft(
            source_product_id=exact_source.id,
            source_variant_asin="B000TEST02",
            source_variant_attributes_json={"Size": "2.5 ML"},
            target_site_id="CBT",
            target_category_id="CBT414038",
            title="Existing exact variant draft",
            content_version=4,
        )
        db.add(exact_draft)
        db.commit()
        parent_id = parent.id
        exact_source_id = exact_source.id
        exact_draft_id = exact_draft.id

    response = client.post(
        f"/api/imports/source-products/{parent_id}/variants/B000TEST02/collection-job",
        json={"target_site_id": "CBT", "collector_kind": "browser_extension"},
    )

    assert response.status_code == 200
    assert response.json()["source_product_id"] == exact_source_id
    assert response.json()["draft_id"] == exact_draft_id
    with testing_session() as db:
        assert db.query(SourceProduct).count() == 2
        assert db.query(ProductDraft).count() == 1
        job = db.query(CollectionJob).one()
        assert job.source_product_id == exact_source_id
        assert job.draft_id == exact_draft_id


def test_first_extension_capture_reuses_pending_variant_placeholder():
    client, testing_session = make_client()
    with testing_session() as db:
        parent = SourceProduct(
            source_url="https://www.amazon.com/dp/B000TEST01",
            asin="B000TEST01",
            raw_status=SourceProductStatus.COLLECTED,
            variants_json=[
                {"asin": "B000TEST01", "attributes": {"Size": "1 ML"}},
                {"asin": "B000TEST02", "attributes": {"Size": "2.5 ML"}},
            ],
            title="Measuring spoons",
            image_urls_json=["https://example.test/parent.jpg"],
        )
        db.add(parent)
        db.commit()
        parent_id = parent.id

    queued = client.post(
        f"/api/imports/source-products/{parent_id}/variants/B000TEST02/collection-job",
        json={"target_site_id": "CBT", "collector_kind": "browser_extension"},
    )
    assert queued.status_code == 200
    job_id = queued.json()["id"]
    placeholder_source_id = queued.json()["source_product_id"]
    placeholder_draft_id = queued.json()["draft_id"]

    captured = client.post(
        "/api/imports/amazon-extension/capture",
        json={
            "source_url": "https://www.amazon.com/dp/B000TEST02?ref=variant",
            "target_site_id": "CBT",
            "snapshot": {
                "source_url": "https://www.amazon.com/dp/B000TEST02",
                "title": "2.5 ML stainless steel measuring spoons",
                "images": ["https://images-na.ssl-images-amazon.com/images/I/example._AC_SL1500_.jpg"],
                "variants": [
                    {
                        "asin": "B000TEST02",
                        "attributes": {"Size": "2.5 ML"},
                        "selected": True,
                    }
                ],
            },
        },
    )

    assert captured.status_code == 200
    assert captured.json()["reused"] is True
    assert captured.json()["source_product_id"] == placeholder_source_id
    assert captured.json()["draft_id"] == placeholder_draft_id
    with testing_session() as db:
        assert db.query(SourceProduct).count() == 2
        assert db.query(ProductDraft).count() == 1
        source = db.get(SourceProduct, placeholder_source_id)
        draft = db.get(ProductDraft, placeholder_draft_id)
        job = db.get(CollectionJob, job_id)
        assert source.raw_status == SourceProductStatus.COLLECTED
        assert draft.source_variant_attributes_json == {"Size": "2.5 ML"}
        assert job.status == CollectionJobStatus.COMPLETED
        assert job.source_product_id == placeholder_source_id
        assert job.draft_id == placeholder_draft_id
        assert db.query(AuditEvent).filter_by(
            action="source_product.extension_capture_reused",
            entity_id=str(placeholder_source_id),
        ).count() == 1
        job_event = db.query(AuditEvent).filter_by(
            action="collection_job.extension_finished",
            entity_id=str(job_id),
        ).one()
        assert job_event.after_json["reason"] == "completed_by_first_capture"


def test_extension_job_result_updates_its_variant_placeholder_without_duplicate():
    client, testing_session = make_client()
    with testing_session() as db:
        parent = SourceProduct(
            source_url="https://www.amazon.com/dp/B000TEST01",
            asin="B000TEST01",
            raw_status=SourceProductStatus.COLLECTED,
            variants_json=[
                {"asin": "B000TEST01", "attributes": {"Size": "1 ML"}},
                {"asin": "B000TEST02", "attributes": {"Size": "2.5 ML"}},
            ],
            title="Measuring spoons",
            image_urls_json=["https://example.test/parent.jpg"],
        )
        db.add(parent)
        db.commit()
        parent_id = parent.id

    queued = client.post(
        f"/api/imports/source-products/{parent_id}/variants/B000TEST02/collection-job",
        json={"target_site_id": "CBT", "collector_kind": "browser_extension"},
    )
    assert queued.status_code == 200
    job_id = queued.json()["id"]
    placeholder_source_id = queued.json()["source_product_id"]
    placeholder_draft_id = queued.json()["draft_id"]

    result = client.post(
        f"/api/imports/amazon-extension/jobs/{job_id}/result",
        json={
            "worker_id": "variant-test-worker",
            "source_url": "https://www.amazon.com/dp/B000TEST02",
            "status": "collected",
            "snapshot": {
                "source_url": "https://www.amazon.com/dp/B000TEST02",
                "title": "2.5 ML stainless steel measuring spoons",
                "images": ["https://images-na.ssl-images-amazon.com/images/I/example._AC_SL1500_.jpg"],
                "variants": [
                    {
                        "asin": "B000TEST02",
                        "attributes": {"Size": "2.5 ML"},
                        "selected": True,
                    }
                ],
            },
        },
    )

    assert result.status_code == 200
    assert result.json()["draft_id"] == placeholder_draft_id
    with testing_session() as db:
        assert db.query(SourceProduct).count() == 2
        assert db.query(ProductDraft).count() == 1
        job = db.get(CollectionJob, job_id)
        draft = db.get(ProductDraft, placeholder_draft_id)
        assert job.status == CollectionJobStatus.COMPLETED
        assert job.source_product_id == placeholder_source_id
        assert job.draft_id == placeholder_draft_id
        assert draft.source_variant_attributes_json == {"Size": "2.5 ML"}


def test_repeated_first_extension_capture_does_not_overwrite_edited_draft():
    client, testing_session = make_client()
    payload = {
        "source_url": "https://www.amazon.com/dp/B000TEST01",
        "target_site_id": "CBT",
        "snapshot": {
            "source_url": "https://www.amazon.com/dp/B000TEST01",
            "title": "Original Amazon title",
            "description": "Original Amazon description",
            "images": ["https://images-na.ssl-images-amazon.com/images/I/example._AC_SL1500_.jpg"],
        },
    }
    first = client.post("/api/imports/amazon-extension/capture", json=payload)
    assert first.status_code == 200
    draft_id = first.json()["draft_id"]
    with testing_session() as db:
        draft = db.get(ProductDraft, draft_id)
        draft.title = "Operator edited title"
        draft.description = "Operator edited description"
        draft.content_version += 1
        db.commit()

    repeated_payload = {
        **payload,
        "snapshot": {
            **payload["snapshot"],
            "title": "Late duplicate callback title",
            "description": "Late duplicate callback description",
        },
    }
    repeated = client.post("/api/imports/amazon-extension/capture", json=repeated_payload)

    assert repeated.status_code == 200
    assert repeated.json()["idempotent"] is True
    assert repeated.json()["draft_id"] == draft_id
    with testing_session() as db:
        assert db.query(SourceProduct).count() == 1
        assert db.query(ProductDraft).count() == 1
        draft = db.get(ProductDraft, draft_id)
        assert draft.title == "Operator edited title"
        assert draft.description == "Operator edited description"
        assert db.query(AuditEvent).filter_by(
            action="source_product.extension_duplicate_ignored",
        ).count() == 1


def test_source_variant_collection_job_rejects_unknown_variant():
    client, testing_session = make_client()
    with testing_session() as db:
        source = SourceProduct(
            source_url="https://amazon.com/dp/B000TEST01",
            asin="B000TEST01",
            raw_status=SourceProductStatus.COLLECTED,
            variants_json=[{"asin": "B000TEST01", "attributes": {}}],
        )
        db.add(source)
        db.commit()
        source_id = source.id

    response = client.post(
        f"/api/imports/source-products/{source_id}/variants/B000TEST99/collection-job",
        json={"target_site_id": "MLM"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "source_variant_not_found"
    with testing_session() as db:
        assert db.query(CollectionJob).count() == 0


def test_source_variant_collection_job_persists_variant_page_evidence(monkeypatch):
    client, testing_session = make_client()
    with testing_session() as db:
        source = SourceProduct(
            source_url="https://amazon.com/dp/B000TEST01",
            asin="B000TEST01",
            raw_status=SourceProductStatus.COLLECTED,
            variants_json=[
                {"asin": "B000TEST01", "attributes": {"Color": "Black"}},
                {"asin": "B000TEST02", "attributes": {"Color": "Blue"}},
            ],
        )
        db.add(source)
        db.commit()
        source_id = source.id

    async def collect_variant(source_url: str, target_site_id: str):
        assert source_url == "https://amazon.com/dp/B000TEST02"
        assert target_site_id == "MLB"
        return CollectionResult(
            status=CollectionStatus.COLLECTED,
            source_url=source_url,
            message="collected",
            draft=ProductDraftCreate(
                title="Blue variant",
                target_site_id="MLB",
                source_price=31.5,
                source_currency="USD",
                currency="BRL",
                stock=1,
                image_urls=["https://example.com/blue-hires.jpg"],
            ),
            source_snapshot=AmazonSourceSnapshot(
                source_url=source_url,
                title="Blue variant",
                price={"amount": 31.5, "currency": "USD"},
                images=["https://example.com/blue-hires.jpg"],
                variants=[
                    {
                        "asin": "B000TEST02",
                        "attributes": {"Color": "Blue"},
                        "image_urls": ["https://example.com/blue-hires.jpg"],
                        "selected": True,
                    }
                ],
                measurements={
                    "package_weight": {
                        "value": 2.0,
                        "unit": "lb",
                        "raw": "2 pounds",
                        "source_label": "Shipping Weight",
                    }
                },
            ),
        )

    monkeypatch.setattr(imports, "collect_amazon_page", collect_variant)
    queued = client.post(
        f"/api/imports/source-products/{source_id}/variants/B000TEST02/collection-job",
        json={"target_site_id": "MLB"},
    )
    executed = client.post(f"/api/imports/amazon-url/jobs/{queued.json()['id']}/run")

    assert queued.status_code == 200
    assert executed.status_code == 200
    assert executed.json()["status"] == "completed"
    assert executed.json()["source_product"]["asin"] == "B000TEST02"
    assert executed.json()["source_product"]["source_price"] == 31.5
    resolved = client.post(
        f"/api/imports/source-products/{source_id}/variants/B000TEST02/draft",
        json={"target_site_id": "MLB"},
    )
    assert resolved.status_code == 200
    assert resolved.json()["id"] == executed.json()["draft_id"]
    assert resolved.json()["source_product_id"] == executed.json()["source_product_id"]
    with testing_session() as db:
        collected_source = db.get(SourceProduct, executed.json()["source_product_id"])
        assert collected_source.image_urls_json == ["https://example.com/blue-hires.jpg"]
        assert collected_source.measurements_json["package_weight"]["value"] == 2.0
        draft = db.get(ProductDraft, executed.json()["draft_id"])
        assert draft.source_variant_asin == "B000TEST02"
        assert draft.source_price == 31.5


def test_source_variant_batch_creates_missing_and_reuses_existing_jobs():
    client, testing_session = make_client()
    with testing_session() as db:
        source = SourceProduct(
            source_url="https://www.amazon.com.mx/dp/B000TEST01",
            asin="B000TEST01",
            raw_status=SourceProductStatus.COLLECTED,
            variants_json=[
                {"asin": "B000TEST01", "selected": True},
                {"asin": "B000TEST02", "selected": False},
                {"asin": "B000TEST03", "selected": False},
                {"asin": "B000TEST03", "selected": True},
                {"asin": "B000TEST04", "selected": False},
                {"asin": "B000TEST04", "selected": False},
            ],
        )
        existing = CollectionJob(
            source_url="https://amazon.com.mx/dp/B000TEST02",
            source_identity="https://amazon.com.mx/dp/B000TEST02",
            target_site_id="MLB",
        )
        db.add_all([source, existing])
        db.commit()
        source_id = source.id
        existing_id = existing.id

    first = client.post(
        f"/api/imports/source-products/{source_id}/variants/collection-jobs",
        json={"target_site_id": "MLB"},
    )
    repeated = client.post(
        f"/api/imports/source-products/{source_id}/variants/collection-jobs",
        json={"target_site_id": "MLB"},
    )

    assert first.status_code == 200
    assert first.json()["created_count"] == 1
    assert first.json()["reused_count"] == 1
    assert first.json()["skipped_selected_count"] == 2
    assert [job["source_url"] for job in first.json()["jobs"]] == [
        "https://amazon.com.mx/dp/B000TEST02",
        "https://amazon.com.mx/dp/B000TEST04",
    ]
    assert first.json()["jobs"][0]["id"] == existing_id
    assert repeated.status_code == 200
    assert repeated.json()["created_count"] == 0
    assert repeated.json()["reused_count"] == 2
    assert [job["id"] for job in repeated.json()["jobs"]] == [
        job["id"] for job in first.json()["jobs"]
    ]
    with testing_session() as db:
        assert db.query(CollectionJob).count() == 2


def test_source_variant_batch_honors_variant_asins_subset():
    client, testing_session = make_client()
    with testing_session() as db:
        source = SourceProduct(
            source_url="https://www.amazon.com.mx/dp/B000TEST01",
            asin="B000TEST01",
            raw_status=SourceProductStatus.COLLECTED,
            variants_json=[
                {"asin": "B000TEST01", "selected": True},
                {"asin": "B000TEST02", "selected": False},
                {"asin": "B000TEST03", "selected": False},
                {"asin": "B000TEST04", "selected": False},
            ],
        )
        db.add(source)
        db.commit()
        source_id = source.id

    # Only the requested non-selected variant is enqueued; unknown and selected
    # ASINs in the request are ignored.
    response = client.post(
        f"/api/imports/source-products/{source_id}/variants/collection-jobs",
        json={
            "target_site_id": "MLM",
            "variant_asins": ["B000TEST03", "b000test99", "B000TEST01"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["created_count"] == 1
    assert body["reused_count"] == 0
    assert [job["source_url"] for job in body["jobs"]] == [
        "https://amazon.com.mx/dp/B000TEST03",
    ]
    with testing_session() as db:
        assert db.query(CollectionJob).count() == 1

    # An empty variant_asins list keeps the legacy "all non-selected" behaviour.
    full = client.post(
        f"/api/imports/source-products/{source_id}/variants/collection-jobs",
        json={"target_site_id": "MLB", "variant_asins": []},
    )
    assert full.status_code == 200
    assert full.json()["created_count"] == 3
    assert {job["source_url"] for job in full.json()["jobs"]} == {
        "https://amazon.com.mx/dp/B000TEST02",
        "https://amazon.com.mx/dp/B000TEST03",
        "https://amazon.com.mx/dp/B000TEST04",
    }


def test_collection_job_status_lookup_returns_requested_jobs_and_limits_batch():
    client, testing_session = make_client()
    with testing_session() as db:
        jobs = [
            CollectionJob(source_url=f"https://amazon.com/dp/S{index:09d}", target_site_id="MLM")
            for index in range(3)
        ]
        db.add_all(jobs)
        db.commit()
        job_ids = [job.id for job in jobs]

    response = client.get(
        "/api/imports/amazon-url/jobs/status",
        params=[
            ("job_ids", job_ids[2]),
            ("job_ids", job_ids[0]),
            ("job_ids", job_ids[2]),
            ("job_ids", 999_999),
        ],
    )
    over_limit = client.get(
        "/api/imports/amazon-url/jobs/status",
        params=[("job_ids", index) for index in range(201)],
    )

    assert response.status_code == 200
    assert [job["id"] for job in response.json()] == [job_ids[2], job_ids[0]]
    assert over_limit.status_code == 422
    assert over_limit.json()["detail"] == "collection_job_status_limit_exceeded"


def test_source_variant_batch_rejects_more_than_100_variants():
    client, testing_session = make_client()
    with testing_session() as db:
        source = SourceProduct(
            source_url="https://amazon.com/dp/B000TEST01",
            asin="B000TEST01",
            raw_status=SourceProductStatus.COLLECTED,
            variants_json=[
                {"asin": f"X{index:09d}", "selected": False} for index in range(101)
            ],
        )
        db.add(source)
        db.commit()
        source_id = source.id

    response = client.post(
        f"/api/imports/source-products/{source_id}/variants/collection-jobs",
        json={"target_site_id": "MLM"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "source_variant_batch_limit_exceeded"
    with testing_session() as db:
        assert db.query(CollectionJob).count() == 0


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


def test_amazon_url_file_import_uses_existing_batch_queue_path():
    client, testing_session = make_client()

    response = client.post(
        "/api/imports/amazon-url/jobs/file",
        files={
            "file": (
                "products.csv",
                b"url\nhttps://www.amazon.com/dp/B000TEST01\n"
                b"https://m.amazon.com/gp/product/B000TEST01\n"
                b"https://www.amazon.com.mx/dp/B000TEST02\n",
                "text/csv",
            )
        },
        data={"target_site_id": "MLB", "allow_existing": "false"},
    )

    assert response.status_code == 200
    assert response.json()["created_count"] == 2
    assert response.json()["duplicate_count"] == 1
    with testing_session() as db:
        jobs = db.query(CollectionJob).order_by(CollectionJob.id).all()
        assert [job.target_site_id for job in jobs] == ["MLB", "MLB"]
        assert [job.source_url for job in jobs] == [
            "https://amazon.com/dp/B000TEST01",
            "https://amazon.com.mx/dp/B000TEST02",
        ]


def test_amazon_url_file_import_rejects_unsupported_files_without_writes():
    client, testing_session = make_client()

    response = client.post(
        "/api/imports/amazon-url/jobs/file",
        files={"file": ("products.txt", b"https://amazon.com/dp/B000TEST01", "text/plain")},
        data={"target_site_id": "MLM"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "import_file_type_unsupported"
    with testing_session() as db:
        assert db.query(CollectionJob).count() == 0


def test_amazon_url_file_import_rejects_oversized_request_before_parsing():
    client, testing_session = make_client()

    response = client.post(
        "/api/imports/amazon-url/jobs/file",
        files={"file": ("products.csv", b"x" * (6 * 1024 * 1024), "text/csv")},
        data={"target_site_id": "MLM"},
    )

    assert response.status_code == 413
    assert response.json()["detail"] == "import_request_too_large"
    with testing_session() as db:
        assert db.query(CollectionJob).count() == 0


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
            source_snapshot=AmazonSourceSnapshot(
                source_url=source_url,
                title="Queued Bottle",
                price={"amount": 12.5, "currency": "USD"},
                brand="TrailPro",
                bullets=["Leak proof"],
                images=["https://example.com/a.jpg", "https://example.com/b.jpg"],
                measurements={
                    "item_weight": {
                        "value": 1.2,
                        "unit": "lb",
                        "raw": "1.2 pounds",
                        "source_label": "Item Weight",
                    }
                },
                variants=[
                    {
                        "asin": "B000TEST01",
                        "attributes": {"Color": "Black"},
                        "image_urls": ["https://example.com/black.jpg"],
                        "selected": True,
                    },
                    {
                        "asin": "B000TEST02",
                        "attributes": {"Color": "Blue"},
                        "image_urls": ["https://example.com/blue.jpg"],
                    },
                ],
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
    assert body["source_product"]["collection_method"] == "browser_page"
    assert body["source_product"]["title"] == "Queued Bottle"
    assert body["source_product"]["image_count"] == 2
    assert body["source_product"]["variant_count"] == 2
    assert body["source_product"]["has_snapshot"] is True
    assert body["source_product"]["collection_error"] == ""
    with testing_session() as db:
        source = db.query(SourceProduct).one()
        assert source.raw_status == SourceProductStatus.COLLECTED
        assert source.asin == "B000TEST01"
        assert source.source_price == 12.5
        assert source.source_currency == "USD"
        assert len(source.image_urls_json) == 2
        assert len(source.variants_json) == 2
        assert source.measurements_json["item_weight"]["value"] == 1.2
        initial_draft = db.query(ProductDraft).one()
        assert initial_draft.title == "Queued Bottle"
        assert initial_draft.source_variant_asin == "B000TEST01"
        assert initial_draft.source_variant_attributes_json == {"Color": "Black"}
        assert db.query(CollectionJob).one().status == CollectionJobStatus.COMPLETED

    listed = client.get("/api/imports/amazon-url/jobs")
    assert listed.status_code == 200
    assert listed.json()[0]["source_product"]["brand"] == "TrailPro"
    detail = client.get("/api/imports/source-products/1")
    assert detail.status_code == 200
    assert detail.json()["snapshot"]["title"] == "Queued Bottle"
    assert len(detail.json()["snapshot"]["images"]) == 2
    assert detail.json()["snapshot"]["variants"][1]["attributes"] == {"Color": "Blue"}
    assert detail.json()["snapshot"]["measurements"]["item_weight"]["raw"] == "1.2 pounds"

    variant_draft = client.post(
        "/api/imports/source-products/1/variants/B000TEST02/draft",
        json={"target_site_id": "MLM"},
    )
    assert variant_draft.status_code == 200
    assert variant_draft.json()["source_variant_asin"] == "B000TEST02"

    repeated = client.post(
        "/api/imports/source-products/1/variants/B000TEST02/draft",
        json={"target_site_id": "MLM"},
    )
    assert repeated.status_code == 200
    assert repeated.json()["id"] == variant_draft.json()["id"]
    with testing_session() as db:
        assert db.query(ProductDraft).count() == 2

    missing_variant = client.post(
        "/api/imports/source-products/1/variants/B000TEST99/draft",
        json={"target_site_id": "MLM"},
    )
    assert missing_variant.status_code == 404
    unsupported_site = client.post(
        "/api/imports/source-products/1/variants/B000TEST02/draft",
        json={"target_site_id": "BAD"},
    )
    assert unsupported_site.status_code == 422


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
    assert body["source_product"]["has_snapshot"] is False
    assert "manual action" in body["source_product"]["collection_error"]
    with testing_session() as db:
        source = db.query(SourceProduct).one()
        assert source.raw_status == SourceProductStatus.NEEDS_MANUAL_ACTION
        assert "manual action" in source.collection_error
        assert db.query(ProductDraft).count() == 0
        throttle = db.get(AmazonDomainThrottle, "amazon.com")
        assert throttle.consecutive_challenges == 1
        assert throttle.backoff_until is not None
        assert throttle.last_outcome == "challenge"


def test_collection_persistence_failure_rolls_back_source_and_draft(monkeypatch):
    async def fake_collect(source_url: str, target_site_id: str):
        return CollectionResult(
            status=CollectionStatus.COLLECTED,
            source_url=source_url,
            message="collected",
            draft=ProductDraftCreate(
                title="Atomic Bottle",
                target_site_id=target_site_id,
                source_price=10,
                source_currency="USD",
                currency="MXN",
            ),
            source_snapshot=AmazonSourceSnapshot(
                source_url=source_url,
                title="Atomic Bottle",
                price={"amount": 10, "currency": "USD"},
            ),
        )

    original_create = collection_jobs_service.create_product_draft

    def fail_after_draft_flush(*args, **kwargs):
        original_create(*args, **kwargs)
        raise RuntimeError("simulated persistence interruption")

    monkeypatch.setattr(imports, "collect_amazon_page", fake_collect)
    monkeypatch.setattr(
        collection_jobs_service, "create_product_draft", fail_after_draft_flush
    )
    client, testing_session = make_client()
    created = client.post(
        "/api/imports/amazon-url/jobs",
        json={"source_url": "https://amazon.com/dp/B000TEST01", "target_site_id": "MLM"},
    )

    response = client.post(f"/api/imports/amazon-url/jobs/{created.json()['id']}/run")

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert "persistence failed" in response.json()["message"]
    with testing_session() as db:
        assert db.query(SourceProduct).count() == 0
        assert db.query(ProductDraft).count() == 0
        job = db.query(CollectionJob).one()
        assert job.status == CollectionJobStatus.FAILED
        assert job.source_product_id is None


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
        throttle = db.get(AmazonDomainThrottle, "amazon.com")
        assert throttle.last_outcome == "failed"
        assert throttle.in_flight_until is None
        assert throttle.reservation_id is None


def test_amazon_extension_claim_and_result_are_idempotent_and_audited():
    client, testing_session = make_client()
    with testing_session() as db:
        job = collection_jobs_service.create_collection_jobs(
            db,
            [("https://www.amazon.com/dp/B000TEST01", "CBT")],
            collector_kind="browser_extension",
        )[0]
        job_id = job.id

    claim = client.get("/api/imports/amazon-extension/next", params={"worker_id": "test-worker"})
    assert claim.status_code == 200
    assert claim.json()["job"]["id"] == job_id
    assert claim.json()["job"]["kind"] == "meli_amazon_product"
    empty = client.get("/api/imports/amazon-extension/next", params={"worker_id": "second-worker"})
    assert empty.json()["job"] is None

    result = client.post(
        f"/api/imports/amazon-extension/jobs/{job_id}/result",
        json={
            "worker_id": "test-worker",
            "source_url": "https://www.amazon.com/dp/B000TEST01",
            "status": "collected",
            "snapshot": {
                "source_url": "https://www.amazon.com/dp/B000TEST01",
                "title": "Extension Test Product",
                "price": {"amount": 12.5, "currency": "USD"},
                "description": "A useful test product.",
                "images": ["https://images.example.com/main.jpg"],
                "video_urls": ["https://video.example.com/product.mp4"],
                "variants": [],
                "technical_details": {"Material": "Steel"},
                "measurements": {},
            },
        },
    )
    assert result.status_code == 200
    assert result.json()["status"] == "completed"
    assert result.json()["quality"]["image_count"] == 1
    # An arbitrary page-wide video URL is not product-gallery evidence.
    assert result.json()["quality"]["video_count"] == 0
    repeated = client.post(
        f"/api/imports/amazon-extension/jobs/{job_id}/result",
        json={
            "worker_id": "test-worker",
            "source_url": "https://amazon.com/dp/B000TEST01",
            "status": "collected",
            "snapshot": {},
        },
    )
    assert repeated.status_code == 200
    assert repeated.json()["idempotent"] is True
    with testing_session() as db:
        actions = [event.action for event in db.query(AuditEvent).all()]
        assert "collection_job.created" in actions
        assert "collection_job.extension_claimed" in actions
        assert "collection_job.extension_finished" in actions


def test_automated_extension_campaign_skips_branded_product_without_creating_draft():
    client, testing_session = make_client()
    with testing_session() as db:
        campaign = KeywordCollectionCampaign(
            name="Unbranded overnight test",
            keywords_json=["desk organizer"],
            status="completed",
        )
        db.add(campaign)
        db.flush()
        job = collection_jobs_service.create_collection_jobs(
            db,
            [("https://www.amazon.com/dp/B000TEST01", "CBT")],
            campaign_id=campaign.id,
            campaign_keyword="desk organizer",
            collector_kind="browser_recollect",
        )[0]
        job_id = job.id

    claim = client.get("/api/imports/amazon-extension/next", params={"worker_id": "brand-filter-worker"})
    assert claim.status_code == 200
    result = client.post(
        f"/api/imports/amazon-extension/jobs/{job_id}/result",
        json={
            "worker_id": "brand-filter-worker",
            "source_url": "https://www.amazon.com/dp/B000TEST01",
            "status": "collected",
            "snapshot": {
                "source_url": "https://www.amazon.com/dp/B000TEST01",
                "title": "Useful Desk Organizer",
                "brand": "Example Brand",
                "images": ["https://images.example.com/main.jpg"],
                "variants": [],
                "technical_details": {},
            },
        },
    )

    assert result.status_code == 200
    assert result.json()["status"] == "skipped"
    assert result.json()["skip_reason"] == "source_brand_present"
    assert result.json()["draft_id"] is None
    repeated = client.post(
        f"/api/imports/amazon-extension/jobs/{job_id}/result",
        json={
            "worker_id": "brand-filter-worker",
            "source_url": "https://www.amazon.com/dp/B000TEST01",
            "status": "collected",
            "snapshot": {},
        },
    )
    assert repeated.status_code == 200
    assert repeated.json()["status"] == "skipped"
    assert repeated.json()["idempotent"] is True
    with testing_session() as db:
        job = db.get(CollectionJob, job_id)
        assert job.status == CollectionJobStatus.SKIPPED
        assert "Example Brand" in job.message
        assert db.query(SourceProduct).count() == 0
        assert db.query(ProductDraft).count() == 0
        event = db.query(AuditEvent).filter(
            AuditEvent.action == "collection_job.automated_brand_filtered"
        ).one()
        assert event.after_json["reason"] == "source_brand_present"

    progress = client.get("/api/imports/amazon-search/campaigns")
    assert progress.status_code == 200
    keyword = progress.json()[0]["keywords"][0]
    assert keyword["skipped"] == 1
    assert keyword["processed"] == 1
    assert keyword["status"] == "已完成"

    manual = client.post(
        "/api/imports/amazon-url/jobs",
        json={"source_url": "https://www.amazon.com/dp/B000TEST01", "target_site_id": "CBT"},
    )
    assert manual.status_code == 200
    assert manual.json()["status"] == "pending"
    assert manual.json()["id"] != job_id

    manual_batch = client.post(
        "/api/imports/amazon-url/jobs/batch",
        json={
            "source_urls": ["https://www.amazon.com/dp/B000TEST01"],
            "target_site_id": "CBT",
        },
    )
    # The just-created manual job is now the latest exact-page job, so normal
    # duplicate protection applies again after the filtered campaign terminal.
    assert manual_batch.status_code == 200
    assert manual_batch.json()["existing_count"] == 1


def test_manual_batch_can_requeue_brand_filtered_campaign_result():
    client, testing_session = make_client()
    with testing_session() as db:
        campaign = KeywordCollectionCampaign(
            name="Filtered batch retry",
            keywords_json=["desk organizer"],
            status="completed",
        )
        db.add(campaign)
        db.flush()
        skipped = collection_jobs_service.create_collection_jobs(
            db,
            [("https://www.amazon.com/dp/B000TEST01", "CBT")],
            campaign_id=campaign.id,
            campaign_keyword="desk organizer",
            collector_kind="browser_extension",
        )[0]
        skipped.status = CollectionJobStatus.SKIPPED
        skipped.message = "自动选品已跳过品牌商品：Example Brand"
        db.commit()

    response = client.post(
        "/api/imports/amazon-url/jobs/batch",
        json={
            "source_urls": ["https://www.amazon.com/dp/B000TEST01"],
            "target_site_id": "CBT",
            "collector_kind": "browser_extension",
        },
    )

    assert response.status_code == 200
    assert response.json()["created_count"] == 1
    assert response.json()["existing_count"] == 0
    with testing_session() as db:
        jobs = db.query(CollectionJob).order_by(CollectionJob.id).all()
        assert len(jobs) == 2
        assert jobs[-1].status == CollectionJobStatus.PENDING


def test_operator_extension_job_keeps_branded_product():
    client, testing_session = make_client()
    with testing_session() as db:
        job = collection_jobs_service.create_collection_jobs(
            db,
            [("https://www.amazon.com/dp/B000TEST01", "CBT")],
            collector_kind="browser_extension",
        )[0]
        job_id = job.id

    client.get("/api/imports/amazon-extension/next", params={"worker_id": "operator-worker"})
    result = client.post(
        f"/api/imports/amazon-extension/jobs/{job_id}/result",
        json={
            "worker_id": "operator-worker",
            "source_url": "https://www.amazon.com/dp/B000TEST01",
            "status": "collected",
            "snapshot": {
                "source_url": "https://www.amazon.com/dp/B000TEST01",
                "title": "Operator Requested Product",
                "brand": "Example Brand",
                "images": ["https://images.example.com/main.jpg"],
                "variants": [],
                "technical_details": {},
            },
        },
    )

    assert result.status_code == 200
    assert result.json()["status"] == "completed"
    assert result.json()["draft_id"] is not None
    with testing_session() as db:
        assert db.query(SourceProduct).one().brand == "Example Brand"
        assert db.query(ProductDraft).count() == 1


def test_automated_campaign_accepts_explicit_generic_brand():
    client, testing_session = make_client()
    with testing_session() as db:
        campaign = KeywordCollectionCampaign(
            name="Generic brand test",
            keywords_json=["cable clips"],
            status="completed",
        )
        db.add(campaign)
        db.flush()
        job = collection_jobs_service.create_collection_jobs(
            db,
            [("https://www.amazon.com/dp/B000TEST01", "CBT")],
            campaign_id=campaign.id,
            campaign_keyword="cable clips",
            collector_kind="browser_extension",
        )[0]
        job_id = job.id

    client.get("/api/imports/amazon-extension/next", params={"worker_id": "generic-worker"})
    result = client.post(
        f"/api/imports/amazon-extension/jobs/{job_id}/result",
        json={
            "worker_id": "generic-worker",
            "source_url": "https://www.amazon.com/dp/B000TEST01",
            "status": "collected",
            "snapshot": {
                "source_url": "https://www.amazon.com/dp/B000TEST01",
                "title": "Cable Clips Set",
                "brand": "Brand: Generic",
                "images": ["https://images.example.com/main.jpg"],
                "variants": [],
                "technical_details": {},
            },
        },
    )

    assert result.status_code == 200
    assert result.json()["status"] == "completed"
    with testing_session() as db:
        assert db.query(SourceProduct).one().brand == "Brand: Generic"
        assert db.query(ProductDraft).count() == 1


def test_automated_campaign_uses_title_when_amazon_brand_field_is_missing():
    client, testing_session = make_client()
    with testing_session() as db:
        campaign = KeywordCollectionCampaign(
            name="Missing byline brand test",
            keywords_json=["measuring cup set"],
            status="completed",
        )
        db.add(campaign)
        db.flush()
        job = collection_jobs_service.create_collection_jobs(
            db,
            [("https://www.amazon.com/dp/B000TEST01", "CBT")],
            campaign_id=campaign.id,
            campaign_keyword="measuring cup set",
            collector_kind="browser_extension",
        )[0]
        job_id = job.id

    client.get("/api/imports/amazon-extension/next", params={"worker_id": "title-brand-worker"})
    result = client.post(
        f"/api/imports/amazon-extension/jobs/{job_id}/result",
        json={
            "worker_id": "title-brand-worker",
            "source_url": "https://www.amazon.com/dp/B000TEST01",
            "status": "collected",
            "snapshot": {
                "source_url": "https://www.amazon.com/dp/B000TEST01",
                "title": "KitchenAid Measuring Cup Set",
                "brand": "",
                "images": ["https://images.example.com/main.jpg"],
                "variants": [],
                "technical_details": {},
            },
        },
    )

    assert result.status_code == 200
    assert result.json()["status"] == "skipped"
    assert result.json()["skip_reason"] == "title_brand_suspected"
    with testing_session() as db:
        assert db.query(SourceProduct).count() == 0
        event = db.query(AuditEvent).filter(
            AuditEvent.action == "collection_job.automated_brand_filtered"
        ).one()
        assert event.after_json["source_brand"] == "KitchenAid"
        assert event.after_json["reason"] == "title_brand_suspected"


def test_continuous_campaign_refills_before_extension_goes_idle():
    client, testing_session = make_client()
    with testing_session() as db:
        campaign = KeywordCollectionCampaign(
            name="Continuous refill test",
            target_site_id="CBT",
            keywords_json=["desk organizer"],
            status="continuous",
        )
        db.add(campaign)
        db.commit()
        pool_jobs = collection_jobs_service.create_collection_jobs(
            db,
            [
                ("https://www.amazon.com/dp/B000TEST01", "CBT"),
                ("https://www.amazon.com/dp/B000TEST02", "CBT"),
            ],
            campaign_keyword="desk organizer",
            collector_kind="server",
        )
        for job in pool_jobs:
            job.status = CollectionJobStatus.FAILED
        db.commit()
        campaign_id = campaign.id

    claim = client.get("/api/imports/amazon-recollect/next", params={"worker_id": "continuous-worker"})

    assert claim.status_code == 200
    assert claim.json()["job"] is not None
    assert claim.json()["job"]["campaignId"] == campaign_id
    with testing_session() as db:
        extension_jobs = db.query(CollectionJob).filter(
            CollectionJob.collector_kind == "browser_recollect"
        ).all()
        assert len(extension_jobs) == 2
        assert {job.status for job in extension_jobs} == {
            CollectionJobStatus.RUNNING,
            CollectionJobStatus.PENDING,
        }
        campaign = db.get(KeywordCollectionCampaign, campaign_id)
        assert campaign.status == "continuous"
        assert campaign.queued_count == 2
        actions = [event.action for event in db.query(AuditEvent).all()]
        assert "keyword_campaign.continuous_refilled" in actions


def test_continuous_campaign_pauses_after_ten_consecutive_failures():
    client, testing_session = make_client()
    with testing_session() as db:
        campaign = KeywordCollectionCampaign(
            name="Continuous pause test",
            target_site_id="CBT",
            keywords_json=["desk organizer"],
            status="continuous",
        )
        db.add(campaign)
        db.commit()
        failed_jobs = collection_jobs_service.create_collection_jobs(
            db,
            [
                (f"https://www.amazon.com/dp/B{i:09d}", "CBT")
                for i in range(10)
            ],
            campaign_id=campaign.id,
            campaign_keyword="desk organizer",
            collector_kind="browser_recollect",
        )
        for job in failed_jobs:
            job.status = CollectionJobStatus.FAILED
        db.commit()
        campaign_id = campaign.id

    claim = client.get("/api/imports/amazon-recollect/next", params={"worker_id": "continuous-worker"})

    assert claim.status_code == 200
    assert claim.json()["job"] is None
    with testing_session() as db:
        campaign = db.get(KeywordCollectionCampaign, campaign_id)
        assert campaign.status == "paused"
        assert "连续 10 个" in campaign.message
        assert db.query(AuditEvent).filter(
            AuditEvent.action == "keyword_campaign.continuous_auto_paused"
        ).count() == 1


def test_operator_can_switch_and_pause_continuous_campaign():
    client, testing_session = make_client()
    with testing_session() as db:
        older = KeywordCollectionCampaign(
            name="Older continuous campaign",
            target_site_id="CBT",
            keywords_json=["desk organizer"],
            status="continuous",
        )
        newer = KeywordCollectionCampaign(
            name="New campaign",
            target_site_id="CBT",
            keywords_json=["cable organizer"],
            status="completed",
        )
        db.add_all([older, newer])
        db.commit()
        older_id = older.id
        newer_id = newer.id

    enabled = client.post(f"/api/imports/amazon-search/campaigns/{newer_id}/continuous")

    assert enabled.status_code == 200
    assert enabled.json()["status"] == "continuous"
    with testing_session() as db:
        assert db.get(KeywordCollectionCampaign, older_id).status == "paused"
        assert db.get(KeywordCollectionCampaign, newer_id).status == "continuous"
        assert db.query(AuditEvent).filter(
            AuditEvent.action == "keyword_campaign.continuous_enabled"
        ).count() == 1

    paused = client.post(f"/api/imports/amazon-search/campaigns/{newer_id}/pause")

    assert paused.status_code == 200
    assert paused.json()["status"] == "paused"
    with testing_session() as db:
        assert db.get(KeywordCollectionCampaign, newer_id).status == "paused"
        assert db.query(AuditEvent).filter(
            AuditEvent.action == "keyword_campaign.paused"
        ).count() == 1


def test_listing_recollect_driver_reuses_green_collect_protocol_and_completes_job():
    client, testing_session = make_client()
    with testing_session() as db:
        campaign = KeywordCollectionCampaign(
            name="Listing recollect protocol",
            target_site_id="CBT",
            keywords_json=["desk organizer"],
            status="continuous",
        )
        db.add(campaign)
        db.flush()
        job = collection_jobs_service.create_collection_jobs(
            db,
            [("https://www.amazon.com/dp/B000TEST01", "CBT")],
            campaign_id=campaign.id,
            campaign_keyword="desk organizer",
            collector_kind="browser_recollect",
        )[0]
        job_id = job.id

    claim = client.get(
        "/api/imports/amazon-recollect/next",
        params={"worker_id": "listing-recollect-test"},
    )

    assert claim.status_code == 200
    claimed = claim.json()["job"]
    assert claimed["id"] == job_id
    assert claimed["sourceProductId"] > 0
    source_id = claimed["sourceProductId"]

    captured = client.post(
        f"/api/imports/source-products/{source_id}/extension-capture",
        json={
            "source_url": "https://www.amazon.com/dp/B000TEST01",
            "target_site_id": "CBT",
            "snapshot": {
                "source_url": "https://www.amazon.com/dp/B000TEST01",
                "title": "Adjustable desk cable organizer",
                "price": {"amount": 12.99, "currency": "USD"},
                "bullets": ["Keeps charging cables organized"],
                "description": "Reusable desktop cable holder.",
                "images": ["https://images-na.ssl-images-amazon.com/images/I/example._AC_SL1500_.jpg"],
                "technical_details": {"Material": "Silicone"},
            },
        },
    )

    assert captured.status_code == 200
    assert captured.json()["draft_count"] == 1
    assert captured.json()["completed_collection_job_ids"] == [job_id]
    with testing_session() as db:
        refreshed = db.get(CollectionJob, job_id)
        assert refreshed.status == CollectionJobStatus.COMPLETED
        assert refreshed.draft_id is not None
        assert db.query(ProductDraft).count() == 1
        actions = [event.action for event in db.query(AuditEvent).all()]
        assert "collection_job.listing_recollect_claimed" in actions
        assert "collection_job.listing_recollect_finished" in actions


def test_amazon_extension_recollection_reuses_legacy_draft_without_variant_asin():
    client, testing_session = make_client()
    source_url = "https://www.amazon.com/dp/B000TEST01"
    with testing_session() as db:
        source = SourceProduct(
            source_url=source_url,
            asin="B000TEST01",
            raw_status=SourceProductStatus.NEEDS_MANUAL_ACTION,
            title="Incomplete legacy product",
        )
        db.add(source)
        db.flush()
        draft = ProductDraft(
            source_product_id=source.id,
            source_variant_asin="",
            target_site_id="CBT",
            title="Operator edited title",
            description="Operator edited description",
            risk_status="unreviewed",
        )
        db.add(draft)
        db.flush()
        original_draft_id = draft.id
        job = collection_jobs_service.create_collection_jobs(
            db,
            [(source_url, "CBT")],
            collector_kind="browser_extension",
        )[0]
        job_id = job.id

    claim = client.get("/api/imports/amazon-extension/next", params={"worker_id": "legacy-recollect-worker"})
    assert claim.status_code == 200
    assert claim.json()["job"]["id"] == job_id

    result = client.post(
        f"/api/imports/amazon-extension/jobs/{job_id}/result",
        json={
            "worker_id": "legacy-recollect-worker",
            "source_url": source_url,
            "status": "collected",
            "snapshot": {
                "source_url": source_url,
                "title": "Fresh browser title",
                "description": "Fresh browser description",
                "images": ["https://images.example.com/fresh.jpg"],
                "variants": [],
                "technical_details": {"Material": "Steel"},
            },
        },
    )

    assert result.status_code == 200
    assert result.json()["draft_id"] == original_draft_id
    with testing_session() as db:
        assert db.query(ProductDraft).count() == 1
        refreshed = db.get(ProductDraft, original_draft_id)
        assert refreshed.title == "Fresh browser title"
        assert refreshed.description == "Fresh browser description"
        assert refreshed.image_urls_json == ["https://images.example.com/fresh.jpg"]
