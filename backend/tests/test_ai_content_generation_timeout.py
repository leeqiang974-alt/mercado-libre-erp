import httpx
import pytest
from fastapi import HTTPException
from types import SimpleNamespace

from app.core.config import Settings
from app.services import ai_content_generation
from app.models.product_draft import ProductDraft


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


@pytest.mark.asyncio
async def test_invalid_ai_copy_is_not_automatically_sent_a_second_time(monkeypatch):
    draft = SimpleNamespace(
        id=986,
        target_site_id="CBT",
        target_category_id="CBT414091",
        source_product_id=None,
        title="Cable organizer",
        description="",
        source_variant_attributes_json={},
    )

    class EmptyAuditQuery:
        def filter(self, *_args):
            return self

        def all(self):
            return []

    class FakeDb:
        def get(self, model, _id):
            return draft if model is ProductDraft else None

        def query(self, _model):
            return EmptyAuditQuery()

    requests = 0

    async def invalid_once(**_kwargs):
        nonlocal requests
        requests += 1
        return {
            "title": "Cable Organizer",
            "description": "A short cable organizer description. The store provides a 7-day warranty for this product.",
            "brand": "Unbranded",
        }

    monkeypatch.setattr(ai_content_generation, "get_cached_metadata", lambda *_args: {"verified": True})
    monkeypatch.setattr(
        ai_content_generation,
        "resolve_integration_credentials",
        lambda *_args: SimpleNamespace(deepseek_api_key="test", volcengine_api_key=""),
    )
    monkeypatch.setattr(ai_content_generation, "_request_content", invalid_once)

    with pytest.raises(HTTPException) as caught:
        await ai_content_generation.generate_and_save_draft_content(
            FakeDb(), Settings(), 986, "CBT414091", {"description"}, timeout_seconds=90,
        )

    assert caught.value.status_code == 502
    assert caught.value.detail["code"] == "generated_content_invalid"
    assert requests == 1


@pytest.mark.asyncio
async def test_previously_generated_nonempty_field_does_not_call_ai_again(monkeypatch):
    draft = SimpleNamespace(
        id=986,
        target_site_id="CBT",
        target_category_id="CBT414091",
        source_product_id=None,
        title="Cable organizer",
        description="Existing AI description that the operator has not cleared.",
        source_variant_attributes_json={},
    )

    class GeneratedAuditQuery:
        def filter(self, *_args):
            return self

        def all(self):
            return [({"updated_fields": ["description"]},)]

    class FakeDb:
        def get(self, model, _id):
            return draft if model is ProductDraft else None

        def query(self, _model):
            return GeneratedAuditQuery()

    async def must_not_run(**_kwargs):
        raise AssertionError("a duplicate AI provider request must not be made")

    monkeypatch.setattr(ai_content_generation, "_request_content", must_not_run)

    with pytest.raises(HTTPException) as caught:
        await ai_content_generation.generate_and_save_draft_content(
            FakeDb(), Settings(), 986, "CBT414091", {"description"}, timeout_seconds=90,
        )

    assert caught.value.status_code == 409
    assert caught.value.detail == {"code": "ai_content_already_generated", "fields": ["description"]}


def test_generated_description_rejects_the_old_one_sentence_shape():
    old_description = (
        "This cable management set includes two white TPR cord holder clips. "
        "They are self-adhesive and designed to organize cables on a desk. "
        "The store provides a 7-day warranty for this product."
    )
    with pytest.raises(ValueError, match="80-260 English words"):
        ai_content_generation._validate_generated(
            {"title": "Cable Organizer", "description": old_description, "brand": "Unbranded"},
        )


def test_generated_description_accepts_structured_source_derived_copy():
    description = """This two-piece cable organizer set helps keep charging cords and small wires in place on a desk, nightstand, or work area. Each white TPR holder uses a self-adhesive backing for a simple placement process on a clean, dry surface.

Key details:
- Includes two white TPR cord holder clips.
- Self-adhesive design for cable routing.
- Intended for organizing phone charger, computer, and desk cables.

Suitable uses: Use the clips at home, in an office, in a car, or beside a computer where loose charging and accessory cords need a fixed resting point.
The store provides a 7-day warranty for this product."""

    content = ai_content_generation._validate_generated(
        {"title": "Cable Organizer Clips", "description": description, "brand": "Unbranded"},
    )

    assert content.description == description
