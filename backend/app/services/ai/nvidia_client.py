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


class NvidiaReviewClient:
    prompt_version = REVIEW_PROMPT_VERSION

    def __init__(
        self,
        api_key: str = "",
        model: str = "meta/llama-3.1-70b-instruct",
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.api_key = api_key
        self.model = model
        self.transport = transport

    async def pre_screen_draft(self, draft: ProductDraftCreate) -> ReviewResponse:
        if not self.api_key:
            raise AIProviderError("nvidia", "api_key_required")
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": review_prompt(draft.model_dump_json()),
                }
            ],
            "temperature": 0,
            "max_tokens": 800,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "content-type": "application/json",
        }
        try:
            async with httpx.AsyncClient(transport=self.transport, timeout=45) as client:
                response = await client.post(
                    "https://integrate.api.nvidia.com/v1/chat/completions",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
        except Exception as exc:
            raise provider_request_error("nvidia", exc) from exc
        data: dict = {}
        try:
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("NVIDIA response must be a JSON object")
            data = payload
            text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            parsed = parse_review_json("nvidia", text)
            input_tokens, output_tokens, total_tokens = token_usage(data)
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
                "nvidia",
                "invalid_response",
                http_status=200,
                request_id=provider_request_id(response, data),
            ) from exc
