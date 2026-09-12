from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.audit_event import AuditEvent
from app.models.meli_metadata_cache import MeliMetadataCache
from app.models.product_draft import ProductDraft
from app.models.publish_job import PublishJob, PublishJobStatus
from app.services.ai_content_generation import generate_and_save_draft_content
from app.services.audit_events import create_audit_event
from app.services.meli.metadata_cache import category_attributes_key


PREFILL_PROVIDERS = ("agnes", "volcengine")
PREFILL_FAILURE_ACTION = "draft.ai_content_prefill_failed"
PREFILL_SUCCESS_ACTION = "draft.ai_content_prefill_completed"
PREFILL_MAX_FAILURE_ROUNDS = 6


def _generated_fields_by_draft(db: Session, draft_ids: list[int]) -> dict[int, set[str]]:
    if not draft_ids:
        return {}
    rows = db.execute(
        select(AuditEvent.entity_id, AuditEvent.after_json).where(
            AuditEvent.entity_type == "product_draft",
            AuditEvent.action == "draft.ai_content_generated",
            AuditEvent.entity_id.in_([str(value) for value in draft_ids]),
        )
    ).all()
    result: dict[int, set[str]] = {}
    for entity_id, after in rows:
        if not isinstance(after, dict):
            continue
        try:
            draft_id = int(entity_id)
        except (TypeError, ValueError):
            continue
        result.setdefault(draft_id, set()).update(
            field for field in after.get("updated_fields", [])
            if field in {"title", "description"}
        )
    return result


def _failure_state(db: Session, draft_ids: list[int]) -> dict[int, tuple[int, datetime | None]]:
    if not draft_ids:
        return {}
    rows = db.execute(
        select(AuditEvent.entity_id, AuditEvent.created_at, AuditEvent.after_json).where(
            AuditEvent.entity_type == "product_draft",
            AuditEvent.action == PREFILL_FAILURE_ACTION,
            AuditEvent.entity_id.in_([str(value) for value in draft_ids]),
        ).order_by(AuditEvent.id)
    ).all()
    result: dict[int, tuple[int, datetime | None]] = {}
    for entity_id, created_at, after in rows:
        provider_errors = after.get("provider_errors", {}) if isinstance(after, dict) else {}
        # Missing verified category metadata is a prerequisite wait, not an AI
        # attempt. Historical rows with this result must not permanently use
        # up the retry budget once the metadata becomes available.
        if provider_errors and set(map(str, provider_errors.values())) <= {
            "category_attributes_not_verified"
        }:
            continue
        try:
            draft_id = int(entity_id)
        except (TypeError, ValueError):
            continue
        count, _ = result.get(draft_id, (0, None))
        result[draft_id] = (count + 1, created_at)
    return result


def _eligible_drafts(db: Session) -> list[ProductDraft]:
    drafts = list(db.scalars(
        select(ProductDraft)
        .where(
            ProductDraft.target_site_id == "CBT",
            ProductDraft.target_category_id.like("CBT%"),
            ~exists(
                select(PublishJob.id).where(
                    PublishJob.product_draft_id == ProductDraft.id,
                    PublishJob.status == PublishJobStatus.PUBLISHED,
                )
            ),
        )
        .order_by(ProductDraft.id.desc())
    ).all())
    cache_keys = {
        category_attributes_key(draft.target_category_id.strip().upper())
        for draft in drafts
    }
    verified_keys = {
        row.cache_key
        for row in db.scalars(
            select(MeliMetadataCache).where(MeliMetadataCache.cache_key.in_(cache_keys))
        ).all()
        if isinstance(row.payload_json, dict) and row.payload_json.get("verified") is True
    }
    return [
        draft
        for draft in drafts
        if category_attributes_key(draft.target_category_id.strip().upper()) in verified_keys
    ]


async def run_ai_content_prefill_pass(db: Session, limit: int = 1) -> dict[str, int]:
    """Prefill unpublished CBT drafts so the editor opens with final AI copy."""
    settings = get_settings()
    drafts = _eligible_drafts(db)
    generated = _generated_fields_by_draft(db, [draft.id for draft in drafts])
    failures = _failure_state(db, [draft.id for draft in drafts])
    now = datetime.now(UTC)
    selected: list[ProductDraft] = []
    pending_total = 0
    for draft in drafts:
        existing = generated.get(draft.id, set())
        if "title" in existing and draft.title.strip() and "description" in existing and draft.description.strip():
            continue
        failure_rounds, last_failed_at = failures.get(draft.id, (0, None))
        if failure_rounds >= PREFILL_MAX_FAILURE_ROUNDS:
            continue
        pending_total += 1
        if last_failed_at is not None:
            if last_failed_at.tzinfo is None:
                last_failed_at = last_failed_at.replace(tzinfo=UTC)
            cooldown = timedelta(minutes=min(10 * (2 ** max(0, failure_rounds - 1)), 360))
            if now < last_failed_at + cooldown:
                continue
        if len(selected) < max(1, limit):
            selected.append(draft)

    summary = {"processed": 0, "completed": 0, "failed": 0, "remaining": 0}
    for candidate in selected:
        summary["processed"] += 1
        provider_errors: dict[str, str] = {}
        completed = False
        for provider in PREFILL_PROVIDERS:
            try:
                _draft, _content, _model, meta = await generate_and_save_draft_content(
                    db,
                    settings,
                    candidate.id,
                    candidate.target_category_id,
                    {"title", "description"},
                    timeout_seconds=settings.ai_content_generation_timeout_seconds,
                    provider_override=provider,
                )
                create_audit_event(
                    db=db,
                    actor_type="system",
                    actor_id="ai-content-worker",
                    action=PREFILL_SUCCESS_ACTION,
                    entity_type="product_draft",
                    entity_id=str(candidate.id),
                    after={
                        "provider": provider,
                        "provider_order": list(PREFILL_PROVIDERS),
                        "updated_fields": meta.get("updated_fields", []),
                        "attempt_counts": meta.get("attempt_counts", {}),
                    },
                )
                summary["completed"] += 1
                completed = True
                break
            except HTTPException as exc:
                db.rollback()
                detail = exc.detail
                code = detail.get("code") if isinstance(detail, dict) else detail
                normalized_code = str(code or "generation_failed")[:120]
                if normalized_code == "ai_content_already_generated":
                    create_audit_event(
                        db=db,
                        actor_type="system",
                        actor_id="ai-content-worker",
                        action=PREFILL_SUCCESS_ACTION,
                        entity_type="product_draft",
                        entity_id=str(candidate.id),
                        after={
                            "provider": "preserved-existing",
                            "provider_order": list(PREFILL_PROVIDERS),
                            "updated_fields": [],
                            "attempt_counts": {},
                        },
                    )
                    summary["completed"] += 1
                    completed = True
                    break
                provider_errors[provider] = normalized_code
                # Category and draft validation failures are deterministic and
                # provider-independent; fallback would only repeat the same
                # local gate. Fall back only after an actual provider/output
                # failure from Agnes.
                if provider == "agnes" and not (
                    normalized_code.startswith("agnes_")
                    or normalized_code == "generated_content_invalid"
                ):
                    break
            except Exception:
                db.rollback()
                provider_errors[provider] = "internal_error"
        if completed:
            continue
        previous_failures = failures.get(candidate.id, (0, None))[0]
        create_audit_event(
            db=db,
            actor_type="system",
            actor_id="ai-content-worker",
            action=PREFILL_FAILURE_ACTION,
            entity_type="product_draft",
            entity_id=str(candidate.id),
            after={
                "failure_round": previous_failures + 1,
                "provider_order": list(PREFILL_PROVIDERS),
                "provider_errors": provider_errors,
            },
        )
        summary["failed"] += 1

    summary["remaining"] = max(0, pending_total - summary["completed"])
    return summary
