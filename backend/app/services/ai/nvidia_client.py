import httpx

from app.schemas.drafts import ProductDraftCreate
from app.schemas.reviews import ReviewResponse
from app.services.ai.provider_utils import AIProviderError, parse_review_json, review_prompt


class NvidiaReviewClient:
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
                data = response.json()
        except Exception as exc:
            raise AIProviderError("nvidia", "request_failed") from exc
        text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        try:
            return parse_review_json("nvidia", text)
        except Exception as exc:
            raise AIProviderError("nvidia", "invalid_response") from exc
