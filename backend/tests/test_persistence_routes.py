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
from app.models.registry import import_all_models
from app.models.source_product import SourceProduct, SourceProductStatus
from app.models.store import Store
from app.models.token_credential import TokenCredential
from app.schemas.drafts import ProductDraftCreate
from app.services.amazon.collector import CollectionResult, CollectionStatus
from app.services.meli.oauth import MercadoLibreOAuthClient
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


def test_import_amazon_html_can_persist_and_list_draft():
    client, testing_session = make_client()

    response = client.post(
        "/api/imports/amazon-html",
        json={
            "source_url": "https://www.amazon.com/dp/B000TEST",
            "html": "<span id='productTitle'>Persisted Bottle</span><span class='a-price'><span class='a-offscreen'>$9.99</span></span><img id='landingImage' src='https://example.com/a.jpg' />",
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


def test_oauth_callback_persists_store_without_returning_tokens(monkeypatch):
    client, testing_session = make_client()

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "access_token": "access-token",
                "refresh_token": "refresh-token",
                "expires_in": 21600,
                "user_id": 456,
            },
        )

    def fake_client() -> MercadoLibreOAuthClient:
        return MercadoLibreOAuthClient(
            client_id="client-123",
            client_secret="secret-456",
            redirect_uri="http://localhost:8000/api/stores/meli/callback",
            transport=httpx.MockTransport(handler),
        )

    monkeypatch.setattr(stores, "create_oauth_client", fake_client)
    monkeypatch.setattr(stores.settings, "token_encryption_key", "test-secret")

    response = client.get("/api/stores/meli/callback?code=code-789&state=state-abc")

    assert response.status_code == 200
    assert response.json()["seller_id"] == "456"
    assert "access-token" not in response.text
    assert "refresh-token" not in response.text

    stores_response = client.get("/api/stores")
    assert stores_response.status_code == 200
    assert stores_response.json()[0]["seller_id"] == "456"
    assert stores_response.json()[0]["token_reference"] == "meli:456"

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
            "source_url": "https://www.amazon.com/dp/B000TEST",
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
            "source_url": "https://www.amazon.com/dp/B000TEST",
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
