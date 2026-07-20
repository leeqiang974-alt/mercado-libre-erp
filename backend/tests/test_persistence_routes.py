import httpx
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import stores
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.product_draft import ProductDraft
from app.models.audit_event import AuditEvent
from app.models.collection_job import CollectionJob, CollectionJobStatus
from app.models.registry import import_all_models
from app.models.source_product import SourceProduct, SourceProductStatus
from app.models.store import Store
from app.models.token_credential import TokenCredential
from app.schemas.drafts import ProductDraftCreate
from app.services.drafts import create_product_draft
from app.services.amazon.collector import CollectionResult, CollectionStatus
from app.services.meli.oauth import MercadoLibreOAuthClient, create_state_token
from app.services.meli.client import MercadoLibreClient
from app.services.meli.token_vault import resolve_store_access_token


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


def test_target_price_is_never_backfilled_as_amazon_source_evidence():
    _, testing_session = make_client()
    with testing_session() as db:
        draft = create_product_draft(
            db,
            ProductDraftCreate(
                title="Manual target offer",
                price=500,
                currency="MXN",
            ),
        )

    assert draft.source_price is None
    assert draft.source_currency == ""
    assert draft.price == 500
    assert draft.currency == "MXN"
    assert draft.condition == ""
    assert draft.stock == 0


def test_import_amazon_html_can_persist_and_list_draft():
    client, testing_session = make_client()

    response = client.post(
        "/api/imports/amazon-html",
        json={
            "source_url": "https://www.amazon.com/dp/B000TEST01",
            "html": "<input id='ASIN' value='B000TEST01' /><span id='productTitle'>Persisted Bottle</span><span class='a-price'><span class='a-offscreen'>$9.99</span></span><img id='landingImage' src='https://example.com/a.jpg' />",
            "target_site_id": "MLM",
            "persist": True,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == 1
    assert body["draft"]["title"] == "Persisted Bottle"

    list_response = client.get("/api/drafts")
    assert list_response.status_code == 200
    assert list_response.json()[0]["title"] == "Persisted Bottle"

    with Session(testing_session.kw["bind"]) as session:
        assert session.query(ProductDraft).count() == 1
        source = session.query(SourceProduct).one()
        assert source.raw_status == SourceProductStatus.NEEDS_MANUAL_ACTION
        assert "not independently fetched" in source.collection_error
        assert session.query(ProductDraft).one().source_product_id == source.id


def test_import_amazon_html_resolves_manual_collection_job_atomically():
    client, testing_session = make_client()
    source_url = "https://www.amazon.com/dp/B000TEST01"
    with testing_session() as db:
        old_source = SourceProduct(
            source_url=source_url,
            asin="B000TEST01",
            raw_status=SourceProductStatus.NEEDS_MANUAL_ACTION,
            collection_error="Amazon challenge detected",
        )
        db.add(old_source)
        db.flush()
        job = CollectionJob(
            source_url=source_url,
            source_identity=source_url,
            target_site_id="MLM",
            status=CollectionJobStatus.NEEDS_MANUAL_ACTION,
            message="Amazon challenge detected",
            source_product_id=old_source.id,
        )
        db.add(job)
        db.commit()
        job_id = job.id
        old_source_id = old_source.id

    response = client.post(
        "/api/imports/amazon-html",
        json={
            "source_url": source_url,
            "html": "<input id='ASIN' value='B000TEST01' /><span id='productTitle'>Recovered Bottle</span><span class='a-price'><span class='a-offscreen'>$9.99</span></span><img id='landingImage' src='https://example.com/a.jpg' />",
            "target_site_id": "MLM",
            "persist": True,
            "collection_job_id": job_id,
        },
    )

    assert response.status_code == 200
    with testing_session() as db:
        job = db.get(CollectionJob, job_id)
        assert job.status == CollectionJobStatus.COMPLETED
        assert job.draft_id == response.json()["id"]
        assert job.source_product_id != old_source_id
        source = db.get(SourceProduct, job.source_product_id)
        assert source.collection_method == "operator_snapshot"
        assert source.title == "Recovered Bottle"
        assert db.get(ProductDraft, job.draft_id).source_product_id == source.id
        audit = (
            db.query(AuditEvent)
            .filter(AuditEvent.action == "collection_job.snapshot_resolved")
            .one()
        )
        assert audit.before_json["source_product_id"] == old_source_id
        assert audit.after_json["source_product_id"] == source.id
        assert audit.after_json["draft_id"] == job.draft_id


def test_import_amazon_html_rejects_invalid_collection_job_binding_without_writes():
    client, testing_session = make_client()
    source_url = "https://www.amazon.com/dp/B000TEST01"
    with testing_session() as db:
        job = CollectionJob(
            source_url=source_url,
            source_identity=source_url,
            target_site_id="MLM",
            status=CollectionJobStatus.NEEDS_MANUAL_ACTION,
        )
        db.add(job)
        db.commit()
        job_id = job.id

    base_payload = {
        "source_url": source_url,
        "html": "<input id='ASIN' value='B000TEST01' /><span id='productTitle'>Bottle</span><span class='a-price'><span class='a-offscreen'>$9.99</span></span><img id='landingImage' src='https://example.com/a.jpg' />",
        "target_site_id": "MLM",
        "persist": True,
        "collection_job_id": job_id,
    }
    not_persisted = client.post(
        "/api/imports/amazon-html",
        json={**base_payload, "persist": False},
    )
    wrong_site = client.post(
        "/api/imports/amazon-html",
        json={**base_payload, "target_site_id": "MLB"},
    )
    wrong_source = client.post(
        "/api/imports/amazon-html",
        json={
            **base_payload,
            "source_url": "https://www.amazon.com/dp/B000TEST02",
            "html": base_payload["html"].replace("B000TEST01", "B000TEST02"),
        },
    )

    assert not_persisted.status_code == 422
    assert not_persisted.json()["detail"] == "snapshot_job_resolution_requires_persist"
    assert wrong_site.status_code == 409
    assert wrong_site.json()["detail"] == "collection_job_site_mismatch"
    assert wrong_source.status_code == 409
    assert wrong_source.json()["detail"] == "collection_job_source_mismatch"
    with testing_session() as db:
        assert db.query(SourceProduct).count() == 0
        assert db.query(ProductDraft).count() == 0
        assert db.get(CollectionJob, job_id).status == CollectionJobStatus.NEEDS_MANUAL_ACTION


def test_import_amazon_html_uses_selected_script_gallery_for_persisted_draft():
    client, testing_session = make_client()
    html = """
    <input id="ASIN" value="B000TEST01" />
    <span id="productTitle">Gallery Bottle</span>
    <span class="a-price"><span class="a-offscreen">$15.00</span></span>
    <script>
      var imageData = {
        "colorImages": {
          "initial": [
            {"hiRes":"https://example.com/main-hires.jpg"},
            {"large":"https://example.com/side-large.jpg"}
          ],
          "Blue": [{"hiRes":"https://example.com/blue-hires.jpg"}]
        },
        "colorToAsin": {"Blue":{"asin":"B000TEST02"}}
      };
    </script>
    """

    response = client.post(
        "/api/imports/amazon-html",
        json={
            "source_url": "https://www.amazon.com/dp/B000TEST01",
            "html": html,
            "target_site_id": "MLM",
            "persist": True,
        },
    )

    assert response.status_code == 200
    assert response.json()["draft"]["image_urls"] == [
        "https://example.com/main-hires.jpg",
        "https://example.com/side-large.jpg",
    ]
    with testing_session() as db:
        source = db.query(SourceProduct).one()
        assert source.image_urls_json == [
            "https://example.com/main-hires.jpg",
            "https://example.com/side-large.jpg",
        ]
        variants = {variant["asin"]: variant for variant in source.variants_json}
        assert variants["B000TEST02"]["image_urls"] == [
            "https://example.com/blue-hires.jpg"
        ]
        draft = db.query(ProductDraft).one()
        assert draft.image_urls_json == source.image_urls_json


def test_import_amazon_html_rejects_non_amazon_and_incomplete_snapshots():
    client, _ = make_client()
    valid_html = "<input id='ASIN' value='B000TEST01' /><span id='productTitle'>Bottle</span><span class='a-price'><span class='a-offscreen'>$9.99</span></span><img id='landingImage' src='https://example.com/a.jpg' />"

    wrong_host = client.post(
        "/api/imports/amazon-html",
        json={
            "source_url": "https://example.com/product/1",
            "html": valid_html,
            "target_site_id": "MLM",
            "persist": True,
        },
    )
    incomplete = client.post(
        "/api/imports/amazon-html",
        json={
            "source_url": "https://www.amazon.com/dp/B000TEST01",
            "html": "<input id='ASIN' value='B000TEST01' /><span id='productTitle'>Bottle</span>",
            "target_site_id": "MLM",
            "persist": True,
        },
    )

    assert wrong_host.status_code == 422
    assert wrong_host.json()["detail"] == "only_public_amazon_product_urls_allowed"
    assert incomplete.status_code == 422
    assert incomplete.json()["detail"] == "amazon_snapshot_incomplete:price,image"


def test_import_amazon_html_rejects_challenge_page():
    client, testing_session = make_client()

    response = client.post(
        "/api/imports/amazon-html",
        json={
            "source_url": "https://www.amazon.com/dp/B000TEST01",
            "html": "<html><title>Robot Check</title><p>Enter the characters you see below</p></html>",
            "target_site_id": "MLM",
            "persist": True,
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "amazon_challenge_snapshot_rejected"
    with testing_session() as db:
        assert db.query(SourceProduct).count() == 0
        assert db.query(ProductDraft).count() == 0


def test_import_amazon_html_rejects_asin_identity_mismatch():
    client, _ = make_client()
    html = "<input id='ASIN' value='B999OTHER1' /><span id='productTitle'>Bottle</span><span class='a-price'><span class='a-offscreen'>$9.99</span></span><img id='landingImage' src='https://example.com/a.jpg' />"

    response = client.post(
        "/api/imports/amazon-html",
        json={
            "source_url": "https://www.amazon.com/dp/B000TEST01",
            "html": html,
            "target_site_id": "MLM",
            "persist": True,
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "amazon_snapshot_identity_mismatch"


def test_oauth_callback_persists_store_without_returning_tokens(monkeypatch):
    monkeypatch.setattr(stores.settings, "meli_client_id", "client-123")
    monkeypatch.setattr(stores.settings, "meli_client_secret", "secret-456")
    client, testing_session = make_client()

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/users/me":
            return httpx.Response(200, json={"id": 456, "site_id": "MLM"})
        return httpx.Response(
            200,
            json={
                "access_token": "access-token",
                "refresh_token": "refresh-token",
                "expires_in": 21600,
                "user_id": 456,
            },
        )

    def fake_client(db=None) -> MercadoLibreOAuthClient:
        return MercadoLibreOAuthClient(
            client_id="client-123",
            client_secret="secret-456",
            redirect_uri="http://localhost:8000/api/stores/meli/callback",
            transport=httpx.MockTransport(handler),
        )

    monkeypatch.setattr(stores, "create_oauth_client", fake_client)
    monkeypatch.setattr(
        stores,
        "create_meli_client",
        lambda access_token: MercadoLibreClient(
            access_token=access_token,
            transport=httpx.MockTransport(handler),
        ),
    )
    monkeypatch.setattr(stores.settings, "token_encryption_key", "test-secret")

    state = create_state_token(stores.settings.token_encryption_key, "MLM")
    response = client.get(
        f"/api/stores/meli/callback?code=code-789&state={state}",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].endswith("seller_id=456&site_id=MLM")
    assert "access-token" not in response.text
    assert "refresh-token" not in response.text

    stores_response = client.get("/api/stores")
    assert stores_response.status_code == 200
    assert stores_response.json()[0]["seller_id"] == "456"
    assert "token_reference" not in stores_response.json()[0]

    with Session(testing_session.kw["bind"]) as session:
        assert session.query(Store).count() == 1
        store = session.query(Store).one()
        credential = session.query(TokenCredential).one()
        assert credential.store_id == store.id
        assert credential.token_reference == "meli:456"
        assert "access-token" not in credential.encrypted_access_token
        assert "refresh-token" not in credential.encrypted_refresh_token
        assert resolve_store_access_token(session, store, "test-secret") == "access-token"


def test_import_amazon_url_can_persist_collected_draft(monkeypatch):
    from app.api.routes import imports

    client, testing_session = make_client()

    async def fake_collect(source_url: str, target_site_id: str):
        return CollectionResult(
            status=CollectionStatus.COLLECTED,
            source_url=source_url,
            message="collected",
            draft=ProductDraftCreate(
                title="Persisted URL Bottle",
                target_site_id=target_site_id,
                price=11.5,
                currency="USD",
                stock=1,
                image_urls=["https://example.com/a.jpg"],
            ),
        )

    monkeypatch.setattr(imports, "collect_amazon_page", fake_collect)

    response = client.post(
        "/api/imports/amazon-url",
        json={
            "source_url": "https://www.amazon.com/dp/B000TEST01",
            "target_site_id": "MLM",
            "persist": True,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "collected"
    assert body["draft_id"] == 1
    assert body["source_product_id"] == 1

    with Session(testing_session.kw["bind"]) as session:
        source = session.query(SourceProduct).one()
        draft = session.query(ProductDraft).one()
        assert source.raw_status == SourceProductStatus.COLLECTED
        assert draft.source_product_id == source.id


def test_import_amazon_url_persists_manual_action_without_draft(monkeypatch):
    from app.api.routes import imports

    client, testing_session = make_client()

    async def fake_collect(source_url: str, target_site_id: str):
        return CollectionResult(
            status=CollectionStatus.NEEDS_MANUAL_ACTION,
            source_url=source_url,
            message="Amazon challenge detected; manual action required.",
            draft=None,
        )

    monkeypatch.setattr(imports, "collect_amazon_page", fake_collect)

    response = client.post(
        "/api/imports/amazon-url",
        json={
            "source_url": "https://www.amazon.com/dp/B000TEST01",
            "target_site_id": "MLM",
            "persist": True,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "needs_manual_action"
    assert body["draft_id"] is None
    assert body["source_product_id"] == 1

    with Session(testing_session.kw["bind"]) as session:
        source = session.query(SourceProduct).one()
        assert source.raw_status == SourceProductStatus.NEEDS_MANUAL_ACTION
        assert session.query(ProductDraft).count() == 0
