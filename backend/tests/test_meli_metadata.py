import httpx
import pytest

from app.services.meli.client import MercadoLibreClient
from app.services.meli.metadata import (
    fetch_available_listing_types,
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
async def test_listing_types_keep_only_supported_classic_and_premium():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {"id": "gold_pro"},
                {"id": "free"},
                {"id": "gold_special"},
                {"id": "gold_pro"},
                {"name": "missing id"},
            ],
        )

    result = await fetch_listing_type_ids(
        MercadoLibreClient(transport=httpx.MockTransport(handler)),
        "MLM",
    )

    assert result == ["gold_pro", "gold_special"]


@pytest.mark.asyncio
async def test_listing_types_reject_non_list_response():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"id": "gold_pro"})

    with pytest.raises(ValueError, match="invalid_listing_types_response"):
        await fetch_listing_type_ids(
            MercadoLibreClient(transport=httpx.MockTransport(handler)),
            "MLM",
        )


@pytest.mark.asyncio
async def test_available_listing_types_are_scoped_and_filter_non_commercial_types():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/users/seller-1/available_listing_types"
        assert request.url.params["category_id"] == "MLM123"
        return httpx.Response(
            200,
            json={
                "category_id": "MLM123",
                "available": [
                    {
                        "site_id": "MLM",
                        "id": "gold_special",
                        "name": "Clásica",
                        "remaining_listings": None,
                    },
                    {"site_id": "MLM", "id": "free", "name": "Gratuita"},
                ],
            },
        )

    result = await fetch_available_listing_types(
        MercadoLibreClient(transport=httpx.MockTransport(handler)),
        "seller-1",
        "MLM123",
    )

    assert result == {
        "category_id": "MLM123",
        "listing_types": [
            {
                "id": "gold_special",
                "name": "Clásica",
                "site_id": "MLM",
                "remaining_listings": None,
            }
        ],
    }


@pytest.mark.asyncio
async def test_available_listing_types_reject_category_mismatch():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"category_id": "MLA123", "available": []},
        )

    with pytest.raises(ValueError, match="available_listing_types_category_mismatch"):
        await fetch_available_listing_types(
            MercadoLibreClient(transport=httpx.MockTransport(handler)),
            "seller-1",
            "MLM123",
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("listing_type", "error"),
    [
        (
            {"id": "gold_special", "name": "Clásica", "remaining_listings": None},
            "available_listing_type_site_missing",
        ),
        (
            {
                "site_id": "MLM",
                "id": "gold_special",
                "name": "Clásica",
                "remaining_listings": -1,
            },
            "invalid_remaining_listings",
        ),
    ],
)
async def test_available_listing_types_require_strict_provider_evidence(
    listing_type,
    error,
):
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"category_id": "MLM123", "available": [listing_type]},
        )

    with pytest.raises(ValueError, match=error):
        await fetch_available_listing_types(
            MercadoLibreClient(transport=httpx.MockTransport(handler)),
            "seller-1",
            "MLM123",
        )


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
