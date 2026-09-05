import asyncio
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
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
    category_predictions_key,
    category_tree_key,
    get_cached_metadata,
    upsert_cached_metadata,
)
from app.services.meli.cbt import normalize_cbt_profile
from app.services.meli.category_catalog import (
    browse_category_catalog,
    category_catalog_key,
    search_category_catalog,
    sync_category_catalog,
)
from app.services.meli.category_i18n import (
    add_category_translations,
    translate_category_names_with_ai,
    translate_category_payload_names,
    translate_category_query,
    translate_category_text,
)

router = APIRouter(prefix="/api/stores", tags=["stores"])
settings = get_settings()


class StoreOperationsUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    is_enabled: bool | None = None


def create_oauth_client(db: Session) -> MercadoLibreOAuthClient:
    credentials = resolve_integration_credentials(db, settings)
    return MercadoLibreOAuthClient(
        client_id=credentials.meli_client_id,
        client_secret=credentials.meli_client_secret,
        redirect_uri=settings.meli_redirect_uri,
    )


def create_meli_client(access_token: str, timeout: float = 30) -> MercadoLibreClient:
    return MercadoLibreClient(access_token=access_token, timeout=timeout)


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
def list_stores(db: Session = Depends(get_db)) -> list[dict[str, object]]:
    return [
        {
            "id": str(store.id),
            "site_id": store.site_id,
            "seller_id": store.seller_id,
            "display_name": store.display_name,
            "oauth_status": store.oauth_status,
            "is_enabled": store.is_enabled,
        }
        for store in db.query(Store).order_by(Store.id.desc()).all()
    ]


@router.patch("/{store_id}")
def update_store_operations(store_id: int, payload: StoreOperationsUpdate, db: Session = Depends(get_db)) -> dict[str, object]:
    store = db.get(Store, store_id)
    if store is None:
        raise HTTPException(status_code=404, detail="Store not found.")
    if payload.display_name is not None:
        store.display_name = " ".join(payload.display_name.split())
    if payload.is_enabled is not None:
        store.is_enabled = payload.is_enabled
    db.commit()
    return {"id": str(store.id), "site_id": store.site_id, "seller_id": store.seller_id, "display_name": store.display_name, "oauth_status": store.oauth_status, "is_enabled": store.is_enabled}


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


@router.get("/{store_id}/cbt/category-predictions")
async def get_cbt_category_predictions(
    store_id: int,
    q: str = Query(..., min_length=1, max_length=180),
    mode: str = Query(default="smart"),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """Use the authenticated CBT domain-discovery endpoint documented for Global Selling."""
    original_query = " ".join(q.split())
    query, query_supported = translate_category_query(original_query)
    # Keep Chinese input usable even when it is outside the small local query
    # dictionary. The marketplace endpoint remains the source of truth; known
    # Chinese terms are translated before calling it and unknown terms are sent
    # through unchanged for the API to interpret or return no candidates.
    store = db.get(Store, store_id)
    if store is None or store.site_id.strip().upper() != "CBT":
        raise HTTPException(status_code=422, detail="A connected CBT Global Selling store is required.")
    if store.oauth_status != "connected":
        raise HTTPException(status_code=409, detail="Store is not connected.")
    catalog = get_cached_metadata(db, category_catalog_key("CBT"))
    if mode == "manual":
        predictions = search_category_catalog(catalog or {}, original_query)
        if not predictions:
            raise HTTPException(
                status_code=409,
                detail="分类全量缓存尚未完成，或缓存中没有匹配结果。",
            )
        return {
            "store_id": store.id,
            "query": original_query,
            "query_en": query,
            "source": "category_catalog_cache",
            "predictions": predictions,
        }
    cached = get_cached_metadata(db, category_predictions_key("CBT", query))
    if isinstance(cached, dict) and isinstance(cached.get("predictions"), list) and cached.get("translation_version") == 2:
        return {"store_id": store.id, "query": original_query, "query_en": query, "source": "cache", "predictions": cached["predictions"]}
    try:
        access_token = await resolve_fresh_store_access_token(
            db=db, store=store, encryption_key=settings.token_encryption_key,
            oauth_client=create_oauth_client(db),
        )
        if not access_token:
            raise HTTPException(status_code=409, detail="Store access token is unavailable.")
        data = await create_meli_client(access_token, timeout=10).get(
            f"/marketplace/domain_discovery/search?q={quote(query, safe='')}"
        )
    except HTTPException:
        raise
    except (httpx.HTTPError, asyncio.TimeoutError) as exc:
        # MercadoLibre domain-discovery is slow or unreachable. Fall back to the
        # local category catalog so the editor never shows a bare 504.
        fallback = search_category_catalog(catalog or {}, original_query)
        if fallback:
            return {
                "store_id": store.id,
                "query": original_query,
                "query_en": query,
                "source": "category_catalog_fallback",
                "predictions": fallback,
            }
        raise HTTPException(status_code=502, detail="CBT category prediction is unavailable.") from exc
    if not isinstance(data, list):
        raise HTTPException(status_code=502, detail="CBT category prediction returned an invalid response.")
    predictions = []
    for item in data[:12]:
        if not isinstance(item, dict) or not str(item.get("category_id") or "").strip().upper().startswith("CBT"):
            continue
        predictions.append({
            **item,
            "category_name_zh": translate_category_text(item.get("category_name") or item.get("domain_name")),
            "domain_name_zh": translate_category_text(item.get("domain_name")),
            "parent_path_zh": translate_category_text(item.get("parent_path")),
        })
    names = [str(item.get("category_name") or item.get("domain_name") or "") for item in predictions]
    names += [str(item.get("parent_path") or "") for item in predictions]
    translations = await translate_category_names_with_ai(names, settings.agnes_api_key, settings.agnes_base_url, settings.agnes_model)
    for item in predictions:
        item["category_name_zh"] = translations.get(str(item.get("category_name") or item.get("domain_name") or ""), item.get("category_name_zh", ""))
        item["domain_name_zh"] = translations.get(str(item.get("domain_name") or ""), item.get("domain_name_zh", ""))
        item["parent_path_zh"] = " > ".join(translations.get(part.strip(), part.strip()) for part in str(item.get("parent_path") or "").split(">"))
    upsert_cached_metadata(db, category_predictions_key("CBT", query), {"site_id": "CBT", "query": query, "translation_version": 2, "predictions": predictions})
    return {"store_id": store.id, "query": original_query, "query_en": query, "source": "mercado_libre_api", "predictions": predictions}


@router.post("/{store_id}/cbt/category-cache/sync")
async def sync_cbt_category_cache(
    store_id: int, db: Session = Depends(get_db)
) -> dict[str, object]:
    """Prewarm the global CBT bilingual category catalog from one authorized store."""
    store = db.get(Store, store_id)
    if store is None or store.site_id.strip().upper() != "CBT":
        raise HTTPException(status_code=422, detail="A connected CBT Global Selling store is required.")
    if store.oauth_status != "connected":
        raise HTTPException(status_code=409, detail="Store is not connected.")
    try:
        access_token = await resolve_fresh_store_access_token(
            db=db, store=store, encryption_key=settings.token_encryption_key,
            oauth_client=create_oauth_client(db),
        )
        if not access_token:
            raise HTTPException(status_code=409, detail="Store access token is unavailable.")
        payload = await sync_category_catalog(
            db, create_meli_client(access_token), "CBT",
            settings.agnes_api_key, settings.agnes_base_url, settings.agnes_model,
        )
        return {
            "store_id": store.id,
            "site": "CBT",
            "source": "mercadolibre_api",
            "node_count": len(payload["nodes"]),
            "complete": payload["complete"],
            "translation_version": payload["translation_version"],
            "translated_by": payload["translated_by"],
        }
    except HTTPException:
        raise
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(status_code=502, detail="CBT category cache sync failed.") from exc


@router.get("/{store_id}/cbt/category-tree")
async def get_cbt_category_tree(
    store_id: int, category_id: str = Query(default=""), db: Session = Depends(get_db)
) -> dict[str, object]:
    """Browse the authorized seller's CBT root or one category's children."""
    store = db.get(Store, store_id)
    if store is None or store.site_id.strip().upper() != "CBT":
        raise HTTPException(status_code=422, detail="A connected CBT Global Selling store is required.")
    if store.oauth_status != "connected":
        raise HTTPException(status_code=409, detail="Store is not connected.")
    normalized = category_id.strip().upper()
    if normalized and not normalized.startswith("CBT"):
        raise HTTPException(status_code=422, detail="CBT category ID is required.")
    cache_key = category_tree_key("CBT", normalized)
    cached = get_cached_metadata(db, cache_key)
    catalog = get_cached_metadata(db, category_catalog_key("CBT"))
    if isinstance(catalog, dict) and catalog.get("complete") is True:
        return {**browse_category_catalog(catalog, normalized), "store_id": store.id}
    if isinstance(cached, dict) and isinstance(cached.get("children"), list) and cached.get("translation_version") == 3:
        return {**cached, "store_id": store.id, "source": "cache"}
    try:
        access_token = await resolve_fresh_store_access_token(
            db=db, store=store, encryption_key=settings.token_encryption_key,
            oauth_client=create_oauth_client(db),
        )
        if not access_token:
            raise HTTPException(status_code=409, detail="Store access token is unavailable.")
        client = create_meli_client(access_token)
        if normalized:
            detail = await client.get(f"/categories/{normalized}")
            if not isinstance(detail, dict):
                raise ValueError("invalid_category_response")
            translated = await translate_category_payload_names(
                detail, settings.agnes_api_key, settings.agnes_base_url, settings.agnes_model
            )
            translated_children = await translate_category_payload_names(
                {"children": detail.get("children_categories", [])},
                settings.agnes_api_key, settings.agnes_base_url, settings.agnes_model,
            )
            payload = {
                "category": translated,
                "children": translated_children.get("children", []),
                "translation_version": 3,
            }
            upsert_cached_metadata(db, cache_key, {**payload, "site_id": "CBT", "translation_version": 3})
            return {**payload, "store_id": store.id, "source": "mercado_libre_api"}
        roots = await client.get("/sites/CBT/categories")
    except HTTPException:
        raise
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(status_code=502, detail="CBT category tree is unavailable.") from exc
    if not isinstance(roots, list):
        raise HTTPException(status_code=502, detail="CBT category tree returned an invalid response.")
    payload = await translate_category_payload_names({
        "category": None,
        "children": [
            child
            for child in roots if isinstance(child, dict)
        ],
        "translation_version": 3,
    }, settings.agnes_api_key, settings.agnes_base_url, settings.agnes_model)
    upsert_cached_metadata(db, cache_key, {**payload, "site_id": "CBT", "translation_version": 3})
    return {**payload, "store_id": store.id, "source": "mercado_libre_api"}


@router.get("/{store_id}/cbt/categories/{category_id}/marketplace-listing-types")
async def get_cbt_marketplace_listing_types(
    store_id: int, category_id: str, db: Session = Depends(get_db)
) -> dict[str, object]:
    """Return the official available Classic/Premium types for every CBT Remote market.

    An unavailable remote response is reported per market; it is never replaced
    with a Premium default.
    """
    store = db.get(Store, store_id)
    if store is None:
        raise HTTPException(status_code=404, detail="Store not found.")
    if store.site_id.strip().upper() != "CBT":
        raise HTTPException(status_code=422, detail="This endpoint is only for CBT Global Selling stores.")
    normalized_category_id = category_id.strip().upper()
    if not normalized_category_id.startswith("CBT"):
        raise HTTPException(status_code=422, detail="Global Selling listing types require a CBT category.")
    try:
        access_token = await resolve_fresh_store_access_token(
            db=db, store=store, encryption_key=settings.token_encryption_key,
            oauth_client=create_oauth_client(db),
        )
        if not access_token:
            raise HTTPException(status_code=409, detail="Store access token is unavailable.")
        client = create_meli_client(access_token)
        user, marketplaces, capacity = await asyncio.wait_for(asyncio.gather(
            client.get(f"/users/{store.seller_id}"),
            client.get(f"/marketplace/users/{store.seller_id}"),
            client.get("/marketplace/users/cap"),
        ), timeout=5)
        profile = normalize_cbt_profile(store.seller_id, user, marketplaces, capacity)
    except HTTPException:
        raise
    except (httpx.HTTPError, TimeoutError) as exc:
        raise HTTPException(status_code=502, detail="Global Selling marketplaces are unavailable.") from exc

    async def lookup(market: dict[str, object]) -> dict[str, object]:
        site_id = str(market.get("site_id") or "")
        seller_id = str(market.get("seller_id") or "")
        if not market.get("available") or not seller_id:
            return {"site_id": site_id, "verified": False, "listing_type_ids": [], "error": "market_unavailable"}
        try:
            result = await asyncio.wait_for(
                fetch_available_listing_types(client, seller_id, normalized_category_id), timeout=4
            )
            ids = [str(item.get("id")) for item in result["listing_types"] if str(item.get("id")) in {"gold_special", "gold_pro"}]
            return {"site_id": site_id, "verified": True, "listing_type_ids": ids}
        except (httpx.HTTPError, TimeoutError, ValueError):
            return {"site_id": site_id, "verified": False, "listing_type_ids": [], "error": "official_listing_types_unavailable"}

    markets = [item for item in profile["marketplaces"] if isinstance(item, dict)]
    return {
        "store_id": store.id,
        "category_id": normalized_category_id,
        "markets": await asyncio.gather(*(lookup(item) for item in markets)),
    }


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


@router.get("/{store_id}/items/{item_id}/price-reference")
async def get_store_item_price_reference(
    store_id: int,
    item_id: str,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """Read Mercado Libre's optional price benchmark for one CBT item.

    A 404 is a documented normal outcome: Mercado Libre only produces a
    benchmark for eligible items.  It must not be presented as a zero-cost
    quote or a backend failure in the operator UI.
    """
    store = db.get(Store, store_id)
    if store is None:
        raise HTTPException(status_code=404, detail="Store not found.")
    if store.site_id.strip().upper() != "CBT":
        raise HTTPException(status_code=422, detail="Price references are currently available for CBT Global Selling stores only.")
    if store.oauth_status != "connected":
        raise HTTPException(status_code=409, detail="Store is not connected.")
    normalized_item_id = item_id.strip().upper()
    if not normalized_item_id.startswith("CBT"):
        raise HTTPException(status_code=422, detail="Price reference lookup starts from a CBT parent item.")

    try:
        access_token = await resolve_fresh_store_access_token(
            db=db,
            store=store,
            encryption_key=settings.token_encryption_key,
            oauth_client=create_oauth_client(db),
        )
        if not access_token:
            raise HTTPException(status_code=409, detail="Store access token is unavailable.")
        result = await create_meli_client(access_token).get(
            f"/marketplace/benchmarks/items/{normalized_item_id}/details"
        )
    except HTTPException:
        raise
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 400:
            return {
                "store_id": store.id,
                "item_id": normalized_item_id,
                "availability": "unavailable",
                "reason": "requires_marketplace_child_item",
                "message": "Price references apply to active marketplace child items, not directly to the CBT parent item.",
            }
        if exc.response.status_code == 404:
            return {
                "store_id": store.id,
                "item_id": normalized_item_id,
                "availability": "unavailable",
                "reason": "official_no_reference",
                "message": "Mercado Libre has not provided a price reference for this item.",
            }
        if exc.response.status_code in {403, 412}:
            return {
                "store_id": store.id,
                "item_id": normalized_item_id,
                "availability": "unavailable",
                "reason": "not_eligible_or_not_authorized",
                "message": "Mercado Libre did not make a price reference available for this item.",
            }
        raise HTTPException(status_code=502, detail="Mercado Libre price reference is unavailable.") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Mercado Libre price reference is unavailable.") from exc

    if not isinstance(result, dict):
        raise HTTPException(status_code=502, detail="Mercado Libre returned an invalid price reference.")
    current_price = result.get("current_price") if isinstance(result.get("current_price"), dict) else {}
    suggested_price = result.get("suggested_price") if isinstance(result.get("suggested_price"), dict) else {}
    estimated_taxes = result.get("estimated_taxes") if isinstance(result.get("estimated_taxes"), dict) else {}
    costs = result.get("costs") if isinstance(result.get("costs"), dict) else {}
    cost_values = [costs.get("selling_fees"), costs.get("shipping_fees"), estimated_taxes.get("amount")]
    can_estimate_after_reference_costs = isinstance(current_price.get("amount"), (int, float)) and all(
        isinstance(value, (int, float)) for value in cost_values
    )
    estimated_after_reference_costs = (
        float(current_price["amount"]) - sum(float(value) for value in cost_values)
        if can_estimate_after_reference_costs
        else None
    )
    return {
        "store_id": store.id,
        "item_id": str(result.get("item_id") or normalized_item_id),
        "availability": "available",
        "status": str(result.get("status") or ""),
        "currency_id": str(result.get("currency_id") or ""),
        "current_price": current_price,
        "suggested_price": suggested_price,
        "lowest_price": result.get("lowest_price") if isinstance(result.get("lowest_price"), dict) else {},
        "estimated_taxes": estimated_taxes,
        "selling_fees": costs.get("selling_fees"),
        "shipping_fees": costs.get("shipping_fees"),
        "percent_difference": result.get("percent_difference"),
        "applicable_suggestion": bool(result.get("applicable_suggestion")),
        "last_updated": str(result.get("last_updated") or ""),
        "estimated_after_reference_costs": estimated_after_reference_costs,
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
