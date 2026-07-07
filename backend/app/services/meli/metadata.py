from app.services.meli.client import MercadoLibreClient


async def fetch_listing_type_ids(client: MercadoLibreClient, site_id: str) -> list[str]:
    data = await client.get(f"/sites/{site_id}/listing_types")
    return [item["id"] for item in data if item.get("id")]


async def predict_category(client: MercadoLibreClient, site_id: str, query: str) -> list[dict]:
    data = await client.get(f"/sites/{site_id}/domain_discovery/search?q={query}")
    return data if isinstance(data, list) else []


async def fetch_category_attributes(client: MercadoLibreClient, category_id: str) -> list[dict]:
    data = await client.get(f"/categories/{category_id}/attributes")
    return data if isinstance(data, list) else []
