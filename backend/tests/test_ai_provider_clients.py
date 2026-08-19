import json

import httpx
import pytest

from app.schemas.drafts import ProductDraftCreate
from app.schemas.reviews import DraftReviewSubject, ReviewListingContext, ReviewPricingContext
from app.services.ai.claude_client import ClaudeReviewClient
from app.services.ai.nvidia_client import NvidiaReviewClient
from app.services.ai.provider_utils import (
    AIProviderError,
    REVIEW_PROMPT_VERSION,
    review_subject_json,
)


def draft():
    return ProductDraftCreate(
        title="Stainless Water Bottle",
        description="Leak proof bottle.",
        target_site_id="MLM",
        price=9.99,
        currency="USD",
        stock=1,
        image_urls=["https://example.com/a.jpg"],
    )


def test_saved_review_subject_contains_publish_evidence_without_credentials():
    subject = DraftReviewSubject(
        draft=draft(),
        pricing=ReviewPricingContext(
            source_price=9.99,
            source_currency="USD",
            target_currency="MXN",
            cost_currency="CNY",
            purchase_cost=100,
            domestic_shipping_cost=20,
            exchange_rate=18,
            purchase_extra_cost=2,
            shipping_cost=50,
            platform_fee_rate=0.15,
            tax_rate=0.05,
            profit_margin_rate=0.2,
            rounding_increment=10,
            landed_cost=231.82,
            target_price=390,
        ),
        listing=ReviewListingContext(
            authorized_store_id=7,
            site_id="MLM",
            category_id="MLM123",
            listing_type_id="gold_pro",
            fulfillment="not_full",
            shipping_mode="me2",
            shipping_logistic_type="drop_off",
            attributes=[{"id": "BRAND", "value_name": "Acme"}],
        ),
    )

    serialized = review_subject_json(subject)
    payload = json.loads(serialized)

    assert payload["pricing"]["exchange_rate"] == 18
    assert payload["listing"]["listing_type_id"] == "gold_pro"
    assert payload["listing"]["shipping_logistic_type"] == "drop_off"
    assert "access_token" not in serialized
    assert "api_key" not in serialized


@pytest.mark.asyncio
async def test_claude_client_posts_messages_request_and_parses_review_json():
    requests = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            headers={"request-id": "req_claude_123"},
            json={
                "id": "msg_claude_123",
                "usage": {"input_tokens": 120, "output_tokens": 30},
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {
                                "decision": "pass",
                                "risk_level": "low",
                                "reason_codes": [],
                                "reasons": ["Looks safe."],
                                "suggested_changes": {},
                            }
                        ),
                    }
                ]
            },
        )

    client = ClaudeReviewClient(api_key="claude-secret", transport=httpx.MockTransport(handler))

    result = await client.review_draft(draft())

    assert result.provider == "claude"
    assert result.decision == "pass"
    assert result.input_tokens == 120
    assert result.output_tokens == 30
    assert result.total_tokens == 150
    assert result.provider_request_id == "req_claude_123"
    assert requests[0].url == "https://api.anthropic.com/v1/messages"
    assert requests[0].headers["x-api-key"] == "claude-secret"
    assert requests[0].headers["anthropic-version"]
    request_body = json.loads(requests[0].content)
    assert REVIEW_PROMPT_VERSION == "meli-safety-v4"
    assert "Never invent product facts" in request_body["system"]
    assert "untrusted marketplace data" in request_body["system"]
    assert "<review_subject>" in request_body["messages"][0]["content"]
    assert "Use pass only" in request_body["system"]
    assert '"pricing":null' in request_body["messages"][0]["content"]
    assert '"listing":null' in request_body["messages"][0]["content"]


@pytest.mark.asyncio
async def test_nvidia_client_posts_chat_completion_and_parses_review_json():
    requests = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            headers={"nvcf-reqid": "req_nvidia_123"},
            json={
                "id": "chatcmpl_nvidia_123",
                "usage": {
                    "prompt_tokens": 90,
                    "completion_tokens": 20,
                    "total_tokens": 110,
                },
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "decision": "needs_human_review",
                                    "risk_level": "medium",
                                    "reason_codes": ["brand_risk"],
                                    "reasons": ["Brand needs manual check."],
                                    "suggested_changes": {"brand": "verify"},
                                }
                            )
                        }
                    }
                ]
            },
        )

    client = NvidiaReviewClient(api_key="nvidia-secret", transport=httpx.MockTransport(handler))

    result = await client.pre_screen_draft(draft())

    assert result.provider == "nvidia"
    assert result.decision == "needs_human_review"
    assert result.reason_codes == ["brand_risk"]
    assert result.input_tokens == 90
    assert result.output_tokens == 20
    assert result.total_tokens == 110
    assert result.provider_request_id == "req_nvidia_123"
    assert requests[0].url == "https://integrate.api.nvidia.com/v1/chat/completions"
    assert requests[0].headers["authorization"] == "Bearer nvidia-secret"
    request_body = json.loads(requests[0].content)
    assert request_body["messages"][0]["role"] == "system"
    assert "untrusted marketplace data" in request_body["messages"][0]["content"]
    assert request_body["messages"][1]["role"] == "user"


@pytest.mark.asyncio
async def test_provider_clients_report_missing_api_key_without_fallback():
    claude = ClaudeReviewClient(api_key="")
    nvidia = NvidiaReviewClient(api_key="")

    with pytest.raises(AIProviderError, match="claude:api_key_required"):
        await claude.review_draft(draft())
    with pytest.raises(AIProviderError, match="nvidia:api_key_required"):
        await nvidia.pre_screen_draft(draft())


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("provider", "client_factory", "method_name"),
    [
        ("claude", ClaudeReviewClient, "review_draft"),
        ("nvidia", NvidiaReviewClient, "pre_screen_draft"),
    ],
)
async def test_provider_clients_preserve_rate_limit_retry_metadata(
    provider, client_factory, method_name
):
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            headers={"retry-after": "17", "request-id": f"req_{provider}_429"},
            json={"error": {"type": "rate_limit_error"}},
        )

    client = client_factory(api_key="secret", transport=httpx.MockTransport(handler))

    with pytest.raises(AIProviderError) as caught:
        await getattr(client, method_name)(draft())

    assert caught.value.code == "rate_limited"
    assert caught.value.http_status == 429
    assert caught.value.retryable is True
    assert caught.value.retry_after_seconds == 17
    assert caught.value.request_id == f"req_{provider}_429"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("provider", "client_factory", "method_name"),
    [
        ("claude", ClaudeReviewClient, "review_draft"),
        ("nvidia", NvidiaReviewClient, "pre_screen_draft"),
    ],
)
@pytest.mark.parametrize("response_body", [b"not-json", b"[]", b'"not-an-object"'])
async def test_provider_clients_classify_malformed_success_as_invalid_response(
    provider, client_factory, method_name, response_body
):
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"request-id": f"req_{provider}_malformed"},
            content=response_body,
        )

    client = client_factory(api_key="secret", transport=httpx.MockTransport(handler))

    with pytest.raises(AIProviderError) as caught:
        await getattr(client, method_name)(draft())

    assert caught.value.code == "invalid_response"
    assert caught.value.http_status == 200
    assert caught.value.retryable is False
    assert caught.value.request_id == f"req_{provider}_malformed"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "review_payload",
    [
        {
            "risk_level": "low",
            "reason_codes": [],
            "reasons": [],
            "suggested_changes": {},
        },
        {
            "decision": "approve",
            "risk_level": "low",
            "reason_codes": [],
            "reasons": [],
            "suggested_changes": {},
        },
        {
            "decision": "pass",
            "risk_level": "unknown",
            "reason_codes": [],
            "reasons": [],
            "suggested_changes": {},
        },
        {
            "decision": "pass",
            "risk_level": "low",
            "reason_codes": [],
            "reasons": [],
            "suggested_changes": {},
            "unexpected": True,
        },
        {
            "decision": "pass",
            "risk_level": "high",
            "reason_codes": ["contradictory"],
            "reasons": ["This must not pass."],
            "suggested_changes": {},
        },
        {
            "decision": "needs_human_review",
            "risk_level": "low",
            "reason_codes": ["contradictory"],
            "reasons": ["This is not low risk."],
            "suggested_changes": {},
        },
    ],
)
@pytest.mark.parametrize(
    ("provider", "client_factory", "method_name"),
    [
        ("claude", ClaudeReviewClient, "review_draft"),
        ("nvidia", NvidiaReviewClient, "pre_screen_draft"),
    ],
)
async def test_provider_clients_fail_closed_on_invalid_review_contract(
    review_payload, provider, client_factory, method_name
):
    async def handler(request: httpx.Request) -> httpx.Response:
        content = json.dumps(review_payload)
        if provider == "claude":
            body = {"content": [{"type": "text", "text": content}]}
        else:
            body = {"choices": [{"message": {"content": content}}]}
        return httpx.Response(
            200,
            headers={"request-id": f"req_{provider}_invalid_contract"},
            json=body,
        )

    client = client_factory(api_key="secret", transport=httpx.MockTransport(handler))

    with pytest.raises(AIProviderError) as caught:
        await getattr(client, method_name)(draft())

    assert caught.value.code == "invalid_response"
    assert caught.value.http_status == 200
    assert caught.value.request_id == f"req_{provider}_invalid_contract"


@pytest.mark.asyncio
async def test_extreme_retry_after_stays_a_structured_rate_limit_error():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            headers={"retry-after": "1e309", "request-id": "req_extreme_retry"},
        )

    client = ClaudeReviewClient(api_key="secret", transport=httpx.MockTransport(handler))

    with pytest.raises(AIProviderError) as caught:
        await client.review_draft(draft())

    assert caught.value.code == "rate_limited"
    assert caught.value.retry_after_seconds is None
    assert caught.value.request_id == "req_extreme_retry"
