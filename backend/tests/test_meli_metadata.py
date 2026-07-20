import httpx
import pytest

from app.services.meli.client import MercadoLibreClient
from app.services.meli.metadata import (
    fetch_category_attributes,
    fetch_listing_type_ids,
    predict_category,
)


@pytest.mark.asyncio
async def test_fetch_listing_type_ids_reads_site_listing_types():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/sites/MLM/listing_types"
        return httpx.Response(200, json=[{"id": "gold_special"}, {"id": "gold_pro"}])

    result = await fetch_listing_type_ids(
        MercadoLibreClient(transport=httpx.MockTransport(handler)),
        "MLM",
    )

    assert result == ["gold_special", "gold_pro"]


@pytest.mark.asyncio
async def test_predict_category_uses_domain_discovery_query():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/sites/MLM/domain_discovery/search"
        assert request.url.params["q"] == "water bottle"
        return httpx.Response(
            200,
            json=[{"category_id": "MLM123", "category_name": "Bottles", "domain_id": "MLM-BOTTLES"}],
        )

    result = await predict_category(
        MercadoLibreClient(transport=httpx.MockTransport(handler)),
        "MLM",
        "water bottle",
    )

    assert result[0]["category_id"] == "MLM123"
    assert result[0]["domain_id"] == "MLM-BOTTLES"


@pytest.mark.asyncio
async def test_fetch_category_attributes_reads_attributes():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/categories/MLM123/attributes"
        return httpx.Response(200, json=[{"id": "BRAND", "name": "Brand", "tags": {"required": True}}])

    result = await fetch_category_attributes(
        MercadoLibreClient(transport=httpx.MockTransport(handler)),
        "MLM123",
    )

    assert result[0]["id"] == "BRAND"
    assert result[0]["tags"]["required"] is True


@pytest.mark.asyncio
async def test_fetch_category_attributes_rejects_malformed_definition():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[{"name": "Missing id", "tags": {"required": True}}],
        )

    with pytest.raises(ValueError, match="invalid_category_attribute_definition"):
        await fetch_category_attributes(
            MercadoLibreClient(transport=httpx.MockTransport(handler)),
            "MLM123",
        )
