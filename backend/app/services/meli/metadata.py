from app.services.meli.client import MercadoLibreClient


async def fetch_listing_type_ids(client: MercadoLibreClient, site_id: str) -> list[str]:
    data = await client.get(f"/sites/{site_id}/listing_types")
    return [item["id"] for item in data if item.get("id")]


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
