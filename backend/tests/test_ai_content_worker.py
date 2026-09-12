from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.audit_event import AuditEvent
from app.models.meli_metadata_cache import MeliMetadataCache
from app.models.product_draft import ProductDraft
from app.models.registry import import_all_models
from app.workers import ai_content_worker
from app.services.meli.metadata_cache import category_attributes_key


def _session():
    import_all_models()
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _add_verified_category(db, category_id: str = "CBT414091"):
    db.add(MeliMetadataCache(
        cache_key=category_attributes_key(category_id),
        payload_json={"verified": True, "attributes": []},
    ))
    db.commit()


@pytest.mark.asyncio
async def test_prefill_uses_agnes_then_volcengine_without_partial_frontend_state(monkeypatch):
    db = _session()
    _add_verified_category(db)
    draft = ProductDraft(
        target_site_id="CBT",
        target_category_id="CBT414091",
        title="Collected source title",
        description="Collected source description",
    )
    db.add(draft)
    db.commit()
    calls: list[str] = []

    async def generate(_db, _settings, draft_id, _category_id, _fields, **kwargs):
        provider = kwargs["provider_override"]
        calls.append(provider)
        if provider == "agnes":
            raise HTTPException(status_code=502, detail={"code": "agnes_timeout"})
        return (
            db.get(ProductDraft, draft_id),
            SimpleNamespace(title="Finished title", description="Finished description"),
            "doubao-test",
            {
                "updated_fields": ["title", "description"],
                "attempt_counts": {"title": 1, "description": 2},
            },
        )

    monkeypatch.setattr(ai_content_worker, "generate_and_save_draft_content", generate)

    summary = await ai_content_worker.run_ai_content_prefill_pass(db, limit=1)

    assert calls == ["agnes", "volcengine"]
    assert summary["completed"] == 1
    event = db.query(AuditEvent).filter(AuditEvent.action == ai_content_worker.PREFILL_SUCCESS_ACTION).one()
    assert event.after_json["provider"] == "volcengine"
    assert event.after_json["attempt_counts"] == {"title": 1, "description": 2}


@pytest.mark.asyncio
async def test_prefill_skips_draft_with_existing_ai_title_and_description(monkeypatch):
    db = _session()
    draft = ProductDraft(
        target_site_id="CBT",
        target_category_id="CBT414091",
        title="Finished title",
        description="Finished description",
    )
    db.add(draft)
    db.commit()
    db.add(AuditEvent(
        actor_type="system",
        actor_id="agnes",
        action="draft.ai_content_generated",
        entity_type="product_draft",
        entity_id=str(draft.id),
        before_json={},
        after_json={"updated_fields": ["title", "description"]},
    ))
    db.commit()

    async def must_not_generate(*_args, **_kwargs):
        raise AssertionError("completed AI fields must not be generated again")

    monkeypatch.setattr(ai_content_worker, "generate_and_save_draft_content", must_not_generate)

    summary = await ai_content_worker.run_ai_content_prefill_pass(db, limit=1)

    assert summary["processed"] == 0


@pytest.mark.asyncio
async def test_prefill_remaining_counts_all_pending_drafts_beyond_pass_limit(monkeypatch):
    db = _session()
    _add_verified_category(db)
    drafts = [
        ProductDraft(
            target_site_id="CBT",
            target_category_id="CBT414091",
            title=f"Collected source title {index}",
            description=f"Collected source description {index}",
        )
        for index in range(3)
    ]
    db.add_all(drafts)
    db.commit()

    async def generate(_db, _settings, draft_id, _category_id, _fields, **_kwargs):
        return (
            db.get(ProductDraft, draft_id),
            SimpleNamespace(title="Finished title", description="Finished description"),
            "agnes-test",
            {"updated_fields": ["title", "description"], "attempt_counts": {}},
        )

    monkeypatch.setattr(ai_content_worker, "generate_and_save_draft_content", generate)

    summary = await ai_content_worker.run_ai_content_prefill_pass(db, limit=1)

    assert summary == {"processed": 1, "completed": 1, "failed": 0, "remaining": 2}


def test_eligible_drafts_wait_for_verified_category_metadata():
    db = _session()
    draft = ProductDraft(
        target_site_id="CBT",
        target_category_id="CBT414091",
        title="Collected source title",
        description="Collected source description",
    )
    db.add(draft)
    db.commit()

    assert ai_content_worker._eligible_drafts(db) == []

    db.add(MeliMetadataCache(
        cache_key=category_attributes_key("CBT414091"),
        payload_json={"verified": True, "attributes": []},
    ))
    db.commit()

    assert [row.id for row in ai_content_worker._eligible_drafts(db)] == [draft.id]


def test_category_metadata_wait_does_not_consume_ai_retry_budget():
    db = _session()
    draft = ProductDraft(
        target_site_id="CBT",
        target_category_id="CBT414091",
        title="Collected source title",
        description="Collected source description",
    )
    db.add(draft)
    db.commit()
    for round_number in range(ai_content_worker.PREFILL_MAX_FAILURE_ROUNDS):
        db.add(AuditEvent(
            actor_type="system",
            actor_id="ai-content-worker",
            action=ai_content_worker.PREFILL_FAILURE_ACTION,
            entity_type="product_draft",
            entity_id=str(draft.id),
            before_json={},
            after_json={
                "failure_round": round_number + 1,
                "provider_errors": {"agnes": "category_attributes_not_verified"},
            },
        ))
    db.commit()

    assert ai_content_worker._failure_state(db, [draft.id]) == {}
