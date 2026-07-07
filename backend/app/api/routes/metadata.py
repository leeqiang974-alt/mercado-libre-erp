from fastapi import APIRouter, Query

from app.services.meli.client import MercadoLibreClient
from app.services.meli.metadata import (
    fetch_category_attributes,
    fetch_listing_type_ids,
    predict_category,
)

router = APIRouter(prefix="/api/metadata", tags=["metadata"])


@router.get("/sites/{site_id}/listing-types")
async def get_listing_types(site_id: str) -> dict[str, list[str]]:
    listing_type_ids = await fetch_listing_type_ids(MercadoLibreClient(), site_id)
    return {"listing_type_ids": listing_type_ids}


@router.get("/sites/{site_id}/category-predictions")
async def get_category_predictions(site_id: str, q: str = Query(...)) -> dict[str, list[dict]]:
    predictions = await predict_category(MercadoLibreClient(), site_id, q)
    return {"predictions": predictions}


@router.get("/categories/{category_id}/attributes")
async def get_category_attributes(category_id: str) -> dict[str, list[dict]]:
    attributes = await fetch_category_attributes(MercadoLibreClient(), category_id)
    return {"attributes": attributes}
