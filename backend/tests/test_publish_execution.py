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
    )

    assert result.status == "blocked"
    assert result.item_id == ""
    assert "live_publish_disabled" in result.errors


@pytest.mark.asyncio
async def test_execute_publish_posts_item_when_enabled():
    requests = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
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
    )

    assert result.status == "published"
    assert result.item_id == "MLM123456"
    assert result.permalink.endswith("MLM-123456")
    assert requests[0].url == "https://api.mercadolibre.com/items"
    assert requests[0].headers["authorization"] == "Bearer access-token"
