import httpx
import pytest
from fastapi import HTTPException

from app.core.config import Settings
from app.services import ai_content_generation


def test_ai_content_timeout_has_a_separate_bounded_default():
    settings = Settings()

    assert settings.api_request_timeout_seconds == 20
    assert settings.ai_content_generation_timeout_seconds == 90


@pytest.mark.asyncio
async def test_provider_read_timeout_is_normalized_as_retryable(monkeypatch):
    class TimeoutClient:
        def __init__(self, *, timeout):
            assert timeout == 37

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def post(self, *_args, **_kwargs):
            raise httpx.ReadTimeout(
                "provider did not respond",
                request=httpx.Request("POST", "https://example.test/chat/completions"),
            )

    monkeypatch.setattr(ai_content_generation.httpx, "AsyncClient", TimeoutClient)

    with pytest.raises(HTTPException) as caught:
        await ai_content_generation._request_content(
            base_url="https://example.test/v1",
            model="deepseek-v4-flash",
            provider="deepseek",
            api_key="test-only",
            prompt="test",
            timeout_seconds=37,
        )

    assert caught.value.status_code == 504
    assert caught.value.detail == {"code": "deepseek_timeout", "retryable": True}
