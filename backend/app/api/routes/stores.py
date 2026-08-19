import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models.store import Store
from app.services.meli.client import MercadoLibreClient
from app.services.integration_credentials import resolve_integration_credentials
from app.services.meli.oauth import (
    MercadoLibreOAuthClient,
    build_authorization_url,
    create_state_token,
    get_state_site_id,
    get_state_code_verifier,
)
from app.services.meli.token_vault import upsert_store_token
from app.services.meli.shipping import list_non_full_shipping_options
from app.services.meli.token_vault import resolve_fresh_store_access_token
from app.services.meli.metadata import fetch_available_listing_types
from app.services.meli.metadata_cache import (
    available_listing_types_key,
    upsert_cached_metadata,
)

router = APIRouter(prefix="/api/stores", tags=["stores"])
settings = get_settings()


def create_oauth_client(db: Session) -> MercadoLibreOAuthClient:
    credentials = resolve_integration_credentials(db, settings)
    return MercadoLibreOAuthClient(
        client_id=credentials.meli_client_id,
        client_secret=credentials.meli_client_secret,
        redirect_uri=settings.meli_redirect_uri,
    )


def create_meli_client(access_token: str) -> MercadoLibreClient:
    return MercadoLibreClient(access_token=access_token)


@router.get("/meli/authorization-url")
def get_meli_authorization_url(
    site_id: str = Query(default=settings.default_site_id),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    credentials = resolve_integration_credentials(db, settings)
    if not credentials.meli_client_id or not credentials.meli_client_secret:
        raise HTTPException(
            status_code=400,
            detail="Mercado Libre application credentials are not configured.",
        )
    normalized_site_id = site_id.strip().upper()
    try:
        # Generate PKCE code_verifier and embed it in the signed state token
        import secrets
        code_verifier = secrets.token_urlsafe(64)
        state = create_state_token(settings.token_encryption_key, normalized_site_id, code_verifier=code_verifier)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Unsupported Mercado Libre site.") from exc
    return {
        "authorization_url": build_authorization_url(
            client_id=credentials.meli_client_id,
            redirect_uri=settings.meli_redirect_uri,
            state=state,
            site_id=normalized_site_id,
            code_verifier=code_verifier,
        ),
        "site_id": normalized_site_id,
    }


@router.get("/meli/callback")
async def meli_callback(
    code: str = Query(...), state: str = Query(...), db: Session = Depends(get_db)
) -> RedirectResponse:
    expected_site_id = get_state_site_id(state, settings.token_encryption_key)
    if expected_site_id is None:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state.")
    credentials = resolve_integration_credentials(db, settings)
    if not credentials.meli_client_id or not credentials.meli_client_secret:
        raise HTTPException(
            status_code=409,
            detail="Mercado Libre application credentials changed during authorization.",
        )
    code_verifier = get_state_code_verifier(state, settings.token_encryption_key)
    token = await create_oauth_client(db).exchange_code(code, code_verifier=code_verifier)
    seller_id = str(token.user_id)
    try:
        profile = await create_meli_client(token.access_token).get("/users/me")
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail="Mercado Libre authorization succeeded but seller site lookup failed.",
        ) from exc
    profile_site_id = str(profile.get("site_id", "")).strip().upper()
    if not profile_site_id:
        raise HTTPException(
            status_code=502,
            detail="Mercado Libre seller profile did not include a site_id.",
        )
    # CBT (全球卖家/跨境店) 特殊处理：
    # 全球卖家授权后，/users/me 返回的是本土站影子用户的 site_id（如 MLM），不是 CBT。
    # 如果请求的是 CBT，且返回了有效的本土站 site_id，也接受，使用 CBT 作为站点。
    if expected_site_id == "CBT":
        site_id = "CBT"
    else:
        site_id = profile_site_id
        if site_id != expected_site_id:
            raise HTTPException(
                status_code=409,
                detail="Authorized seller site does not match the requested site.",
            )
    existing = db.query(Store).filter(Store.seller_id == seller_id).one_or_none()
    if existing:
        existing.site_id = site_id
        existing.oauth_status = "connected"
        existing.display_name = f"Mercado Libre {seller_id}"
        store = existing
    else:
        store = Store(
            site_id=site_id,
            seller_id=seller_id,
            display_name=f"Mercado Libre {seller_id}",
            oauth_status="connected",
        )
        db.add(store)
        db.flush()
    upsert_store_token(
        db=db,
        store=store,
        token=token,
        encryption_key=settings.token_encryption_key,
    )
    db.commit()
    return RedirectResponse(
        url=(
            f"{settings.frontend_url.rstrip('/')}?meli_auth=authorized"
            f"&seller_id={seller_id}&site_id={site_id}"
        ),
        status_code=303,
    )


@router.get("")
def list_stores(db: Session = Depends(get_db)) -> list[dict[str, str]]:
    return [
        {
            "id": str(store.id),
            "site_id": store.site_id,
            "seller_id": store.seller_id,
            "display_name": store.display_name,
            "oauth_status": store.oauth_status,
        }
        for store in db.query(Store).order_by(Store.id.desc()).all()
    ]


@router.get("/{store_id}/categories/{category_id}/listing-types")
async def get_store_category_listing_types(
    store_id: int,
    category_id: str,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    store = db.get(Store, store_id)
    if store is None:
        raise HTTPException(status_code=404, detail="Store not found.")
    if store.oauth_status != "connected":
        raise HTTPException(status_code=409, detail="Store is not connected.")
    normalized_category_id = category_id.strip().upper()
    if not normalized_category_id.startswith(store.site_id.strip().upper()):
        raise HTTPException(status_code=422, detail="Category site does not match store site.")
    try:
        access_token = await resolve_fresh_store_access_token(
            db=db,
            store=store,
            encryption_key=settings.token_encryption_key,
            oauth_client=create_oauth_client(db),
        )
        if not access_token:
            raise HTTPException(status_code=409, detail="Store access token is unavailable.")
        result = await fetch_available_listing_types(
            create_meli_client(access_token),
            store.seller_id,
            normalized_category_id,
        )
    except HTTPException:
        raise
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(
            status_code=502,
            detail="Mercado Libre seller listing types are unavailable.",
        ) from exc
    listing_types = result["listing_types"]
    if any(
        item.get("site_id") and item["site_id"] != store.site_id.strip().upper()
        for item in listing_types
    ):
        raise HTTPException(status_code=502, detail="Mercado Libre listing type site mismatch.")
    payload = {
        "verified": True,
        "store_id": store.id,
        "seller_id": store.seller_id,
        "site_id": store.site_id.strip().upper(),
        "category_id": normalized_category_id,
        "listing_types": listing_types,
    }
    upsert_cached_metadata(
        db,
        available_listing_types_key(store.id, normalized_category_id),
        payload,
    )
    return payload


@router.get("/{store_id}/shipping-options")
async def get_store_shipping_options(
    store_id: int, db: Session = Depends(get_db)
) -> dict[str, object]:
    store = db.get(Store, store_id)
    if store is None:
        raise HTTPException(status_code=404, detail="Store not found.")
    if store.oauth_status != "connected":
        raise HTTPException(status_code=409, detail="Store is not connected.")
    try:
        access_token = await resolve_fresh_store_access_token(
            db=db,
            store=store,
            encryption_key=settings.token_encryption_key,
            oauth_client=create_oauth_client(db),
        )
        if not access_token:
            raise HTTPException(status_code=409, detail="Store access token is unavailable.")
        preferences = await create_meli_client(access_token).get(
            f"/users/{store.seller_id}/shipping_preferences"
        )
    except HTTPException:
        raise
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail="Mercado Libre shipping preferences are unavailable.",
        ) from exc
    options = list_non_full_shipping_options(preferences)
    return {
        "store_id": store.id,
        "site_id": store.site_id,
        "verified": True,
        "options": [
            {"mode": option.mode, "logistic_type": option.logistic_type}
            for option in options
        ],
    }
