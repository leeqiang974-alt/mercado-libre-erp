import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
import httpx
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.meli.client import MercadoLibreClient
from app.services.meli.metadata import (
    fetch_category_attributes,
    fetch_category_details,
    fetch_listing_type_ids,
    predict_category,
)
from app.services.meli.metadata_cache import (
    category_attributes_key,
    category_details_key,
    get_cached_metadata,
    listing_types_key,
    upsert_cached_metadata,
)

router = APIRouter(prefix="/api/metadata", tags=["metadata"])
logger = logging.getLogger(__name__)
STANDARD_LISTING_TYPE_IDS = ["gold_special", "gold_pro"]


def create_metadata_client() -> MercadoLibreClient:
    return MercadoLibreClient(timeout=3)


@router.get("/sites/{site_id}/listing-types")
async def get_listing_types(site_id: str, db: Session = Depends(get_db)) -> dict[str, object]:
    cached = get_cached_metadata(db, listing_types_key(site_id))
    if cached:
        return {
            "listing_type_ids": cached.get("listing_type_ids", []),
            "source": "cache",
            "verified": cached.get("verified") is True,
        }
    return {
        "listing_type_ids": STANDARD_LISTING_TYPE_IDS,
        "source": "standard_catalog",
        "verified": False,
    }


@router.post("/sites/{site_id}/listing-types/refresh")
async def refresh_listing_types(site_id: str, db: Session = Depends(get_db)) -> dict[str, object]:
    return await _fetch_listing_types_with_transparent_fallback(db, site_id)


async def _fetch_listing_types_with_transparent_fallback(
    db: Session, site_id: str
) -> dict[str, object]:
    try:
        listing_type_ids = await asyncio.wait_for(
            fetch_listing_type_ids(create_metadata_client(), site_id),
            timeout=3.5,
        )
    except (httpx.HTTPError, TimeoutError, ValueError) as exc:
        logger.warning("Mercado Libre listing types unavailable for %s: %s", site_id, exc)
        return {
            "listing_type_ids": STANDARD_LISTING_TYPE_IDS,
            "source": "standard_catalog",
            "verified": False,
        }
    if not listing_type_ids:
        logger.warning("Mercado Libre exposes no supported listing types for %s", site_id)
        return {
            "listing_type_ids": [],
            "source": "mercado_libre_api",
            "verified": True,
        }
    payload = {
        "listing_type_ids": listing_type_ids,
        "source": "mercado_libre_api",
        "verified": True,
    }
    upsert_cached_metadata(db, listing_types_key(site_id), payload)
    return payload


@router.get("/sites/{site_id}/category-predictions")
async def get_category_predictions(site_id: str, q: str = Query(...)) -> dict[str, list[dict]]:
    try:
        predictions = await asyncio.wait_for(
            predict_category(create_metadata_client(), site_id, q), timeout=3.5
        )
    except (httpx.HTTPError, TimeoutError) as exc:
        raise _metadata_unavailable("category prediction", exc) from exc
    return {"predictions": predictions}


@router.get("/categories/{category_id}/attributes")
async def get_category_attributes(
    category_id: str, db: Session = Depends(get_db)
) -> dict[str, object]:
    cached = get_cached_metadata(db, category_attributes_key(category_id))
    if cached:
        return {
            "attributes": cached.get("attributes", []),
            "verified": cached.get("verified") is True,
        }
    try:
        attributes = await asyncio.wait_for(
            fetch_category_attributes(create_metadata_client(), category_id), timeout=3.5
        )
    except (httpx.HTTPError, TimeoutError, ValueError) as exc:
        raise _metadata_unavailable("category attributes", exc) from exc
    payload = {"attributes": attributes, "verified": True}
    upsert_cached_metadata(db, category_attributes_key(category_id), payload)
    return payload


@router.get("/categories/{category_id}")
async def get_category_details(
    category_id: str, db: Session = Depends(get_db)
) -> dict[str, object]:
    normalized_category_id = category_id.strip().upper()
    cached = get_cached_metadata(db, category_details_key(normalized_category_id))
    if cached:
        return cached
    try:
        details = await asyncio.wait_for(
            fetch_category_details(create_metadata_client(), normalized_category_id), timeout=3.5
        )
    except (httpx.HTTPError, TimeoutError, ValueError) as exc:
        raise _metadata_unavailable("category details", exc) from exc
    payload = {**details, "verified": True}
    upsert_cached_metadata(db, category_details_key(normalized_category_id), payload)
    return payload


@router.post("/categories/{category_id}/attributes/refresh")
async def refresh_category_attributes(
    category_id: str, db: Session = Depends(get_db)
) -> dict[str, object]:
    try:
        attributes = await asyncio.wait_for(
            fetch_category_attributes(create_metadata_client(), category_id), timeout=3.5
        )
    except (httpx.HTTPError, TimeoutError, ValueError) as exc:
        raise _metadata_unavailable("category attributes", exc) from exc
    payload = {"attributes": attributes, "verified": True}
    upsert_cached_metadata(db, category_attributes_key(category_id), payload)
    return payload


def _metadata_unavailable(operation: str, exc: Exception) -> HTTPException:
    logger.warning("Mercado Libre %s unavailable: %s", operation, exc)
    return HTTPException(
        status_code=503,
        detail={"code": "meli_metadata_unavailable", "operation": operation},
    )
