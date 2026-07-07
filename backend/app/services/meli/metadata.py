from app.services.meli.client import MercadoLibreClient


async def fetch_listing_type_ids(client: MercadoLibreClient, site_id: str) -> list[str]:
    data = await client.get(f"/sites/{site_id}/listing_types")
    return [item["id"] for item in data if item.get("id")]
