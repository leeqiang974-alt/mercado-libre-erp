from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.meli.client import MercadoLibreClient
from app.services.meli.metadata import (
    fetch_category_attributes,
    fetch_listing_type_ids,
    predict_category,
)
from app.services.meli.metadata_cache import (
    category_attributes_key,
    get_cached_metadata,
    listing_types_key,
    upsert_cached_metadata,
)

router = APIRouter(prefix="/api/metadata", tags=["metadata"])


@router.get("/sites/{site_id}/listing-types")
async def get_listing_types(site_id: str, db: Session = Depends(get_db)) -> dict[str, list[str]]:
    cached = get_cached_metadata(db, listing_types_key(site_id))
    if cached:
        return {"listing_type_ids": cached.get("listing_type_ids", [])}
    listing_type_ids = await fetch_listing_type_ids(MercadoLibreClient(), site_id)
    payload = {"listing_type_ids": listing_type_ids}
    upsert_cached_metadata(db, listing_types_key(site_id), payload)
    return payload


@router.post("/sites/{site_id}/listing-types/refresh")
async def refresh_listing_types(site_id: str, db: Session = Depends(get_db)) -> dict[str, list[str]]:
    listing_type_ids = await fetch_listing_type_ids(MercadoLibreClient(), site_id)
    payload = {"listing_type_ids": listing_type_ids}
    upsert_cached_metadata(db, listing_types_key(site_id), payload)
    return payload


@router.get("/sites/{site_id}/category-predictions")
async def get_category_predictions(site_id: str, q: str = Query(...)) -> dict[str, list[dict]]:
    predictions = await predict_category(MercadoLibreClient(), site_id, q)
    return {"predictions": predictions}


@router.get("/categories/{category_id}/attributes")
async def get_category_attributes(
    category_id: str, db: Session = Depends(get_db)
) -> dict[str, list[dict]]:
    cached = get_cached_metadata(db, category_attributes_key(category_id))
    if cached:
        return {"attributes": cached.get("attributes", [])}
    attributes = await fetch_category_attributes(MercadoLibreClient(), category_id)
    payload = {"attributes": attributes}
    upsert_cached_metadata(db, category_attributes_key(category_id), payload)
    return payload


@router.post("/categories/{category_id}/attributes/refresh")
async def refresh_category_attributes(
    category_id: str, db: Session = Depends(get_db)
) -> dict[str, list[dict]]:
    attributes = await fetch_category_attributes(MercadoLibreClient(), category_id)
    payload = {"attributes": attributes}
    upsert_cached_metadata(db, category_attributes_key(category_id), payload)
    return payload
