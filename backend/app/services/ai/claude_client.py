import httpx

from app.schemas.drafts import ProductDraftCreate
from app.schemas.reviews import ReviewResponse
from app.services.ai.review_policy import review_draft_locally
from app.services.ai.provider_utils import parse_review_json, review_prompt


class ClaudeReviewClient:
    def __init__(
        self,
        api_key: str = "",
        model: str = "claude-3-5-sonnet-latest",
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.api_key = api_key
        self.model = model
        self.transport = transport

    async def review_draft(self, draft: ProductDraftCreate) -> ReviewResponse:
        if not self.api_key:
            result = review_draft_locally(draft)
            return result.model_copy(update={"provider": "claude_fallback"})
        payload = {
            "model": self.model,
            "max_tokens": 800,
            "messages": [
                {
                    "role": "user",
                    "content": review_prompt(draft.model_dump_json()),
                }
            ],
        }
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        try:
            async with httpx.AsyncClient(transport=self.transport, timeout=45) as client:
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()
        except Exception:
            result = review_draft_locally(draft)
            return result.model_copy(update={"provider": "claude_fallback"})
        text = "\n".join(
            item.get("text", "") for item in data.get("content", []) if item.get("type") == "text"
        )
        try:
            return parse_review_json("claude", text)
        except Exception:
            result = review_draft_locally(draft)
            return result.model_copy(update={"provider": "claude_fallback"})
