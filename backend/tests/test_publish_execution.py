import httpx
import pytest

from app.schemas.drafts import ProductDraftCreate
from app.schemas.publishing import ListingChoice
from app.services.ai.review_policy import review_draft_locally
from app.services.meli.client import MercadoLibreClient
from app.services.meli.publisher import execute_publish


def valid_draft():
    return ProductDraftCreate(
        title="Stainless Water Bottle",
        description="Leak proof bottle.",
        target_site_id="MLM",
        target_category_id="MLM123",
        price=19.99,
        currency="MXN",
        stock=3,
        image_urls=["https://example.com/a.jpg"],
    )


@pytest.mark.asyncio
async def test_execute_publish_blocks_when_live_publish_disabled():
    draft = valid_draft()
    result = await execute_publish(
        client=MercadoLibreClient(access_token="token"),
        draft=draft,
        review=review_draft_locally(draft),
        listing_choice=ListingChoice(site_id="MLM", listing_type_id="gold_special"),
        valid_listing_type_ids=["gold_special"],
        human_approved=True,
        allow_live_publish=False,
        seller_id="seller-1",
    )

    assert result.status == "blocked"
    assert result.item_id == ""
    assert "live_publish_disabled" in result.errors


@pytest.mark.asyncio
async def test_execute_publish_posts_item_when_enabled():
    requests = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "modes": ["me2"],
                    "logistics": [
                        {
                            "mode": "me2",
                            "types": ["fulfillment", "drop_off"],
                        }
                    ],
                },
            )
        return httpx.Response(
            201,
            json={"id": "MLM123456", "permalink": "https://articulo.mercadolibre.com.mx/MLM-123456"},
        )

    draft = valid_draft()
    result = await execute_publish(
        client=MercadoLibreClient(
            access_token="access-token",
            transport=httpx.MockTransport(handler),
        ),
        draft=draft,
        review=review_draft_locally(draft),
        listing_choice=ListingChoice(site_id="MLM", listing_type_id="gold_special"),
        valid_listing_type_ids=["gold_special", "gold_pro"],
        human_approved=True,
        allow_live_publish=True,
        seller_id="seller-1",
    )

    assert result.status == "published"
    assert result.item_id == "MLM123456"
    assert result.shipping_mode == "me2"
    assert result.permalink.endswith("MLM-123456")
    assert requests[0].url == (
        "https://api.mercadolibre.com/users/seller-1/shipping_preferences"
    )
    assert requests[1].url == "https://api.mercadolibre.com/items"
    assert requests[1].headers["authorization"] == "Bearer access-token"
    assert b'"mode":"me2"' in requests[1].content
    assert b'"free_methods":[]' in requests[1].content


@pytest.mark.asyncio
async def test_execute_publish_blocks_when_store_only_offers_full():
    requests = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "modes": ["me2"],
                "logistics": [{"mode": "me2", "types": ["fulfillment"]}],
            },
        )

    draft = valid_draft()
    result = await execute_publish(
        client=MercadoLibreClient(
            access_token="access-token",
            transport=httpx.MockTransport(handler),
        ),
        draft=draft,
        review=review_draft_locally(draft),
        listing_choice=ListingChoice(site_id="MLM", listing_type_id="gold_special"),
        valid_listing_type_ids=["gold_special"],
        human_approved=True,
        allow_live_publish=True,
        seller_id="seller-1",
    )

    assert result.status == "blocked"
    assert result.errors == ["non_full_shipping_mode_unavailable"]
    assert len(requests) == 1


@pytest.mark.asyncio
async def test_execute_publish_returns_retryable_failure_for_meli_rejection():
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "modes": ["me2"],
                    "logistics": [{"mode": "me2", "types": ["drop_off"]}],
                },
            )
        return httpx.Response(422, json={"message": "validation_error"})

    draft = valid_draft()
    result = await execute_publish(
        client=MercadoLibreClient(
            access_token="access-token",
            transport=httpx.MockTransport(handler),
        ),
        draft=draft,
        review=review_draft_locally(draft),
        listing_choice=ListingChoice(site_id="MLM", listing_type_id="gold_special"),
        valid_listing_type_ids=["gold_special"],
        human_approved=True,
        allow_live_publish=True,
        seller_id="seller-1",
    )

    assert result.status == "failed"
    assert result.shipping_mode == "me2"
    assert result.errors == ["meli_publish_failed:422"]
