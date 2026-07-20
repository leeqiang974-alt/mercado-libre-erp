import httpx

from app.schemas.drafts import ProductDraftCreate
from app.schemas.reviews import ReviewResponse
from app.services.ai.provider_utils import (
    AIProviderError,
    REVIEW_PROMPT_VERSION,
    parse_review_json,
    provider_request_error,
    provider_request_id,
    review_prompt,
    token_usage,
)


class ClaudeReviewClient:
    prompt_version = REVIEW_PROMPT_VERSION

    def __init__(
        self,
        api_key: str = "",
        model: str = "claude-sonnet-4-6",
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.api_key = api_key
        self.model = model
        self.transport = transport

    async def review_draft(self, draft: ProductDraftCreate) -> ReviewResponse:
        if not self.api_key:
            raise AIProviderError("claude", "api_key_required")
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
        except Exception as exc:
            raise provider_request_error("claude", exc) from exc
        data: dict = {}
        try:
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("Claude response must be a JSON object")
            data = payload
            text = "\n".join(
                item.get("text", "")
                for item in data.get("content", [])
                if item.get("type") == "text"
            )
            parsed = parse_review_json("claude", text)
            input_tokens, output_tokens, total_tokens = token_usage(data, anthropic=True)
            return parsed.model_copy(
                update={
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": total_tokens,
                    "provider_request_id": provider_request_id(response, data),
                }
            )
        except Exception as exc:
            raise AIProviderError(
                "claude",
                "invalid_response",
                http_status=200,
                request_id=provider_request_id(response, data),
            ) from exc
