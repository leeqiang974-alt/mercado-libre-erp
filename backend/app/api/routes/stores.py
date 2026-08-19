import asyncio

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
from app.services.meli.cbt import normalize_cbt_profile

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


@router.get("/{store_id}/cbt-publishing-profile")
async def get_cbt_publishing_profile(
    store_id: int, db: Session = Depends(get_db)
) -> dict[str, object]:
    """Read the actual Global Selling publishing model and enabled markets."""
    store = db.get(Store, store_id)
    if store is None:
        raise HTTPException(status_code=404, detail="Store not found.")
    if store.site_id.strip().upper() != "CBT":
        raise HTTPException(status_code=422, detail="This endpoint is only for CBT Global Selling stores.")
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
        client = create_meli_client(access_token)
        user, marketplaces, capacity = await asyncio.gather(
            client.get(f"/users/{store.seller_id}"),
            client.get(f"/marketplace/users/{store.seller_id}"),
            client.get("/marketplace/users/cap"),
        )
    except HTTPException:
        raise
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Global Selling store profile is unavailable.") from exc
    profile = normalize_cbt_profile(store.seller_id, user, marketplaces, capacity)
    profile["store_id"] = store.id
    return profile


@router.get("/{store_id}/items")
async def list_store_items(
    store_id: int,
    limit: int = Query(default=30, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    search: str = Query(default="", max_length=200),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """List real seller items without exposing store credentials to the browser."""
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
        client = create_meli_client(access_token)
        query = f"limit={limit}&offset={offset}"
        if search.strip():
            query += f"&search={httpx.QueryParams({'search': search.strip()})['search']}"
        result = await client.get(f"/users/{store.seller_id}/items/search?{query}")
        if not isinstance(result, dict) or not isinstance(result.get("results"), list):
            raise ValueError("invalid_item_search_response")
        item_ids = [str(item).strip() for item in result["results"] if str(item).strip()]
        detail_path = "/marketplace/items/{}" if store.site_id.strip().upper() == "CBT" else "/items/{}"
        details = await asyncio.gather(
            *(client.get(detail_path.format(item_id)) for item_id in item_ids),
            return_exceptions=True,
        )
    except HTTPException:
        raise
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(status_code=502, detail="Mercado Libre store item list is unavailable.") from exc

    items: list[dict[str, object]] = []
    for item_id, detail in zip(item_ids, details, strict=True):
        if not isinstance(detail, dict):
            items.append({"id": item_id, "load_error": True})
            continue
        pictures = detail.get("pictures") if isinstance(detail.get("pictures"), list) else []
        thumbnail = str(detail.get("thumbnail") or "")
        if not thumbnail and pictures and isinstance(pictures[0], dict):
            thumbnail = str(pictures[0].get("secure_url") or pictures[0].get("url") or "")
        items.append({
            "id": str(detail.get("id") or item_id),
            "title": str(detail.get("title") or ""),
            "thumbnail": thumbnail,
            "status": str(detail.get("status") or ""),
            "category_id": str(detail.get("category_id") or ""),
            "price": detail.get("price"),
            "currency_id": str(detail.get("currency_id") or ""),
            "available_quantity": detail.get("available_quantity"),
            "sold_quantity": detail.get("sold_quantity"),
            "listing_type_id": str(detail.get("listing_type_id") or ""),
            "permalink": str(detail.get("permalink") or ""),
            "warranty": str(detail.get("warranty") or ""),
            "shipping_mode": str((detail.get("shipping") or {}).get("mode") or ""),
            "shipping_logistic_type": str((detail.get("shipping") or {}).get("logistic_type") or ""),
            "free_shipping": bool((detail.get("shipping") or {}).get("free_shipping")),
            "last_updated": str(detail.get("last_updated") or ""),
            "has_public_permalink": bool(detail.get("permalink")),
        })
    paging = result.get("paging") if isinstance(result.get("paging"), dict) else {}
    return {
        "store_id": store.id,
        "site_id": store.site_id,
        "items": items,
        "total": paging.get("total", 0),
        "limit": paging.get("limit", limit),
        "offset": paging.get("offset", offset),
    }


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
