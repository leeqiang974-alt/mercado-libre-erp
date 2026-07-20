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
        if request.url.path.endswith("/description"):
            return httpx.Response(201, content=b"")
        return httpx.Response(
            201,
            json={
                "id": "MLM123456",
                "site_id": "MLM",
                "permalink": "https://articulo.mercadolibre.com.mx/MLM-123456",
                "shipping": {"mode": "me2", "logistic_type": "drop_off"},
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
        valid_listing_type_ids=["gold_special", "gold_pro"],
        human_approved=True,
        allow_live_publish=True,
        seller_id="seller-1",
    )

    assert result.status == "published"
    assert result.item_id == "MLM123456"
    assert result.shipping_mode == "me2"
    assert result.shipping_logistic_type == "drop_off"
    assert result.permalink.endswith("MLM-123456")
    assert requests[0].url == (
        "https://api.mercadolibre.com/users/seller-1/shipping_preferences"
    )
    assert requests[1].url == "https://api.mercadolibre.com/items"
    assert requests[1].headers["authorization"] == "Bearer access-token"
    assert b'"mode":"me2"' in requests[1].content
    assert b'"logistic_type":"drop_off"' in requests[1].content
    assert b'"free_methods":[]' in requests[1].content
    assert b'"description"' not in requests[1].content
    assert requests[2].url == (
        "https://api.mercadolibre.com/items/MLM123456/description"
    )
    assert requests[2].content == b'{"plain_text":"Leak proof bottle."}'


@pytest.mark.asyncio
async def test_execute_publish_closes_item_when_description_is_rejected():
    requests = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "modes": ["me2"],
                    "logistics": [{"mode": "me2", "types": ["drop_off"]}],
                },
            )
        if request.url.path == "/items":
            return httpx.Response(
                201,
                json={
                    "id": "MLM-DESCRIPTION-1",
                    "site_id": "MLM",
                    "shipping": {"mode": "me2", "logistic_type": "drop_off"},
                },
            )
        if request.url.path.endswith("/description"):
            return httpx.Response(422, json={"message": "validation_error"})
        return httpx.Response(200, json={"status": "closed"})

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
    assert result.item_id == "MLM-DESCRIPTION-1"
    assert result.errors == ["meli_description_failed:422"]
    assert requests[-1].method == "PUT"
    assert requests[-1].content == b'{"status":"closed"}'


@pytest.mark.asyncio
async def test_execute_publish_reconciles_lost_description_response():
    requests = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/users/seller-1/shipping_preferences":
            return httpx.Response(
                200,
                json={
                    "modes": ["me2"],
                    "logistics": [{"mode": "me2", "types": ["drop_off"]}],
                },
            )
        if request.url.path == "/items":
            return httpx.Response(
                201,
                json={
                    "id": "MLM-DESCRIPTION-2",
                    "site_id": "MLM",
                    "shipping": {"mode": "me2", "logistic_type": "drop_off"},
                },
            )
        if request.method == "POST":
            raise httpx.ReadTimeout("description response lost", request=request)
        return httpx.Response(200, json={"plain_text": "Leak proof bottle."})

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

    assert result.status == "published"
    assert result.item_id == "MLM-DESCRIPTION-2"
    assert [request.method for request in requests] == ["GET", "POST", "POST", "GET"]


@pytest.mark.asyncio
@pytest.mark.parametrize("description_status", [408, 503])
async def test_execute_publish_reconciles_ambiguous_description_status(
    description_status,
):
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/users/seller-1/shipping_preferences":
            return httpx.Response(
                200,
                json={
                    "modes": ["me2"],
                    "logistics": [{"mode": "me2", "types": ["drop_off"]}],
                },
            )
        if request.url.path == "/items":
            return httpx.Response(
                201,
                json={
                    "id": "MLM-DESCRIPTION-STATUS",
                    "site_id": "MLM",
                    "shipping": {"mode": "me2", "logistic_type": "drop_off"},
                },
            )
        if request.method == "POST":
            return httpx.Response(description_status, json={"message": "ambiguous"})
        return httpx.Response(200, json={"plain_text": "Leak proof bottle."})

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

    assert result.status == "published"
    assert result.item_id == "MLM-DESCRIPTION-STATUS"


@pytest.mark.asyncio
async def test_execute_publish_reconciles_non_json_description_success():
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/users/seller-1/shipping_preferences":
            return httpx.Response(
                200,
                json={
                    "modes": ["me2"],
                    "logistics": [{"mode": "me2", "types": ["drop_off"]}],
                },
            )
        if request.url.path == "/items":
            return httpx.Response(
                201,
                json={
                    "id": "MLM-DESCRIPTION-NONJSON",
                    "site_id": "MLM",
                    "shipping": {"mode": "me2", "logistic_type": "drop_off"},
                },
            )
        if request.method == "POST":
            return httpx.Response(201, content=b"accepted")
        return httpx.Response(200, json={"plain_text": "Leak proof bottle."})

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

    assert result.status == "published"
    assert result.item_id == "MLM-DESCRIPTION-NONJSON"


@pytest.mark.asyncio
async def test_execute_publish_closes_item_when_description_cannot_be_reconciled():
    requests = []
    description_reads = {"count": 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/users/seller-1/shipping_preferences":
            return httpx.Response(
                200,
                json={
                    "modes": ["me2"],
                    "logistics": [{"mode": "me2", "types": ["drop_off"]}],
                },
            )
        if request.url.path == "/items":
            return httpx.Response(
                201,
                json={
                    "id": "MLM-DESCRIPTION-3",
                    "site_id": "MLM",
                    "shipping": {"mode": "me2", "logistic_type": "drop_off"},
                },
            )
        if request.method == "POST":
            raise httpx.ReadTimeout("description response lost", request=request)
        if request.method == "GET":
            description_reads["count"] += 1
            if description_reads["count"] == 1:
                return httpx.Response(200, json=[])
            if description_reads["count"] == 2:
                return httpx.Response(404, json={"message": "description not found"})
            return httpx.Response(200, json={"plain_text": "different text"})
        return httpx.Response(200, json={"status": "closed"})

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
    assert result.item_id == "MLM-DESCRIPTION-3"
    assert result.errors == ["meli_description_outcome_unverified"]
    assert [request.method for request in requests] == [
        "GET",
        "POST",
        "POST",
        "GET",
        "GET",
        "GET",
        "PUT",
    ]


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
async def test_execute_publish_blocks_when_selected_shipping_is_no_longer_available():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "modes": ["me2"],
                "logistics": [{"mode": "me2", "types": ["drop_off"]}],
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
        listing_choice=ListingChoice(
            site_id="MLM",
            listing_type_id="gold_special",
            shipping_mode="me2",
            shipping_logistic_type="self_service",
        ),
        valid_listing_type_ids=["gold_special"],
        human_approved=True,
        allow_live_publish=True,
        seller_id="seller-1",
    )

    assert result.status == "blocked"
    assert result.errors == ["selected_non_full_shipping_option_unavailable"]


@pytest.mark.asyncio
async def test_execute_publish_uses_operator_selected_non_full_shipping():
    requests = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "modes": ["me2"],
                    "logistics": [
                        {"mode": "me2", "types": ["drop_off", "self_service"]}
                    ],
                },
            )
        return httpx.Response(
            201,
            json={
                "id": "MLM-SELECTED-1",
                "site_id": "MLM",
                "shipping": {"mode": "me2", "logistic_type": "self_service"},
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
        listing_choice=ListingChoice(
            site_id="MLM",
            listing_type_id="gold_special",
            shipping_mode="me2",
            shipping_logistic_type="self_service",
        ),
        valid_listing_type_ids=["gold_special"],
        human_approved=True,
        allow_live_publish=True,
        seller_id="seller-1",
    )

    assert result.status == "published"
    assert result.shipping_logistic_type == "self_service"
    assert b'"logistic_type":"self_service"' in requests[1].content


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


@pytest.mark.asyncio
async def test_execute_publish_quarantines_server_error_as_unknown_outcome():
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "modes": ["me2"],
                    "logistics": [{"mode": "me2", "types": ["drop_off"]}],
                },
            )
        return httpx.Response(503, json={"message": "upstream unavailable"})

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
    assert result.errors == ["publish_outcome_unknown_manual_reconciliation_required"]


@pytest.mark.asyncio
async def test_execute_publish_rejects_success_response_without_item_id():
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "modes": ["me2"],
                    "logistics": [{"mode": "me2", "types": ["drop_off"]}],
                },
            )
        return httpx.Response(
            201,
            json={
                "site_id": "MLM",
                "shipping": {"mode": "me2", "logistic_type": "drop_off"},
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
    assert result.errors == [
        "publish_outcome_unknown_manual_reconciliation_required",
        "meli_publish_response_missing_item_id",
    ]


@pytest.mark.asyncio
async def test_execute_publish_closes_item_when_full_is_detected():
    requests = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "modes": ["me2"],
                    "logistics": [
                        {"mode": "me2", "types": ["fulfillment", "drop_off"]}
                    ],
                },
            )
        if request.method == "POST":
            return httpx.Response(
                201,
                json={
                    "id": "MLM-FULL-1",
                    "site_id": "MLM",
                    "shipping": {"mode": "me2", "logistic_type": "fulfillment"},
                },
            )
        return httpx.Response(200, json={"id": "MLM-FULL-1", "status": "closed"})

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
    assert result.item_id == "MLM-FULL-1"
    assert result.errors == ["full_fulfillment_detected"]
    assert requests[-1].method == "PUT"
    assert requests[-1].url.path == "/items/MLM-FULL-1"
    assert requests[-1].content == b'{"status":"closed"}'


@pytest.mark.asyncio
async def test_execute_publish_quarantines_timeout_as_unknown_outcome():
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "modes": ["me2"],
                    "logistics": [{"mode": "me2", "types": ["drop_off"]}],
                },
            )
        raise httpx.ReadTimeout("response lost", request=request)

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
    assert result.errors == ["publish_outcome_unknown_manual_reconciliation_required"]


@pytest.mark.asyncio
async def test_execute_publish_quarantines_protocol_error_as_unknown_outcome():
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "modes": ["me2"],
                    "logistics": [{"mode": "me2", "types": ["drop_off"]}],
                },
            )
        raise httpx.RemoteProtocolError("response stream lost", request=request)

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
    assert result.errors == ["publish_outcome_unknown_manual_reconciliation_required"]


@pytest.mark.asyncio
async def test_execute_publish_quarantines_unverified_full_item_close():
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "modes": ["me2"],
                    "logistics": [{"mode": "me2", "types": ["drop_off"]}],
                },
            )
        if request.method == "POST":
            return httpx.Response(
                201,
                json={
                    "id": "MLM-FULL-2",
                    "site_id": "MLM",
                    "shipping": {"mode": "me2", "logistic_type": "fulfillment"},
                },
            )
        return httpx.Response(200, json={"id": "MLM-FULL-2", "status": "active"})

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
    assert result.item_id == "MLM-FULL-2"
    assert result.errors == [
        "full_fulfillment_detected",
        "meli_item_close_unverified",
        "publish_outcome_unknown_manual_reconciliation_required",
    ]
