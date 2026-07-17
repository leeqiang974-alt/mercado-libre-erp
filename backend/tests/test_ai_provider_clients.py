import json

import httpx
import pytest

from app.schemas.drafts import ProductDraftCreate
from app.services.ai.claude_client import ClaudeReviewClient
from app.services.ai.nvidia_client import NvidiaReviewClient
from app.services.ai.provider_utils import AIProviderError


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


@pytest.mark.asyncio
async def test_claude_client_posts_messages_request_and_parses_review_json():
    requests = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
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
    assert requests[0].url == "https://api.anthropic.com/v1/messages"
    assert requests[0].headers["x-api-key"] == "claude-secret"
    assert requests[0].headers["anthropic-version"]


@pytest.mark.asyncio
async def test_nvidia_client_posts_chat_completion_and_parses_review_json():
    requests = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
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
    assert requests[0].url == "https://integrate.api.nvidia.com/v1/chat/completions"
    assert requests[0].headers["authorization"] == "Bearer nvidia-secret"


@pytest.mark.asyncio
async def test_provider_clients_report_missing_api_key_without_fallback():
    claude = ClaudeReviewClient(api_key="")
    nvidia = NvidiaReviewClient(api_key="")

    with pytest.raises(AIProviderError, match="claude:api_key_required"):
        await claude.review_draft(draft())
    with pytest.raises(AIProviderError, match="nvidia:api_key_required"):
        await nvidia.pre_screen_draft(draft())
