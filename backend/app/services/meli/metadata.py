from app.services.meli.client import MercadoLibreClient
from app.schemas.draft_listing_config import SUPPORTED_LISTING_TYPE_IDS


async def fetch_listing_type_ids(client: MercadoLibreClient, site_id: str) -> list[str]:
    data = await client.get(f"/sites/{site_id}/listing_types")
    if not isinstance(data, list):
        raise ValueError("invalid_listing_types_response")
    listing_type_ids = [
        str(item.get("id") or "").strip().lower()
        for item in data
        if isinstance(item, dict)
    ]
    supported: list[str] = []
    for listing_type_id in listing_type_ids:
        if (
            listing_type_id in SUPPORTED_LISTING_TYPE_IDS
            and listing_type_id not in supported
        ):
            supported.append(listing_type_id)
    return supported


async def fetch_available_listing_types(
    client: MercadoLibreClient,
    seller_id: str,
    category_id: str,
) -> dict[str, object]:
    data = await client.get(
        f"/users/{seller_id}/available_listing_types?category_id={category_id}"
    )
    if not isinstance(data, dict):
        raise ValueError("invalid_available_listing_types_response")
    response_category_id = str(data.get("category_id") or "").strip().upper()
    if response_category_id != category_id.strip().upper():
        raise ValueError("available_listing_types_category_mismatch")
    available = data.get("available")
    if not isinstance(available, list):
        raise ValueError("invalid_available_listing_types_response")
    listing_types: list[dict[str, object]] = []
    seen: set[str] = set()
    for item in available:
        if not isinstance(item, dict):
            raise ValueError("invalid_available_listing_type_definition")
        listing_type_id = str(item.get("id") or "").strip().lower()
        if listing_type_id not in SUPPORTED_LISTING_TYPE_IDS or listing_type_id in seen:
            continue
        site_id = str(item.get("site_id") or "").strip().upper()
        if not site_id:
            raise ValueError("available_listing_type_site_missing")
        remaining_listings = item.get("remaining_listings")
        if (
            remaining_listings is not None
            and (
                isinstance(remaining_listings, bool)
                or not isinstance(remaining_listings, int)
                or remaining_listings < 0
            )
        ):
            raise ValueError("invalid_remaining_listings")
        seen.add(listing_type_id)
        listing_types.append(
            {
                "id": listing_type_id,
                "name": str(item.get("name") or listing_type_id).strip(),
                "site_id": site_id,
                "remaining_listings": remaining_listings,
            }
        )
    return {"category_id": response_category_id, "listing_types": listing_types}


async def predict_category(client: MercadoLibreClient, site_id: str, query: str) -> list[dict]:
    data = await client.get(f"/sites/{site_id}/domain_discovery/search?q={query}")
    return data if isinstance(data, list) else []


async def fetch_category_attributes(client: MercadoLibreClient, category_id: str) -> list[dict]:
    data = await client.get(f"/categories/{category_id}/attributes")
    if not isinstance(data, list):
        raise ValueError("invalid_category_attributes_response")
    for item in data:
        if not isinstance(item, dict) or not str(item.get("id") or "").strip():
            raise ValueError("invalid_category_attribute_definition")
        if "tags" in item and not isinstance(item["tags"], dict):
            raise ValueError("invalid_category_attribute_tags")
        if "values" in item:
            if not isinstance(item["values"], list):
                raise ValueError("invalid_category_attribute_values")
            if any(
                not isinstance(value, dict) or value.get("id") is None
                for value in item["values"]
            ):
                raise ValueError("invalid_category_attribute_value_definition")
    return data
