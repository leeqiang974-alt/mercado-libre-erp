import asyncio
import os
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
from uuid import uuid4
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models.publish_job import PublishJob, PublishJobStatus
from app.models.cbt_listing_config import CbtListingConfig
from app.models.product_draft import ProductDraft
from app.models.store import Store
from app.schemas.drafts import ProductDraftCreate
from app.schemas.cbt_listing_config import CbtListingConfigUpsert
from app.schemas.publishing import (
    ListingChoice,
    PublishBatchEnqueueRequest,
    PublishBatchEnqueueResult,
    PublishBatchItem,
    PublishBatchPreflightItem,
    PublishBatchPreflightRequest,
    PublishBatchPreflightResult,
    PublishExecutionResult,
    PublishJobRead,
    PublishValidationResult,
)
from app.schemas.reviews import ReviewResponse
from app.services.draft_approvals import is_product_draft_approved
from app.services.draft_listing_configs import build_configured_draft
from app.services.cbt_listing_configs import get_cbt_listing_config, resolve_cbt_attribute_value_ids
from app.services.integration_credentials import resolve_integration_credentials
from app.services.audit_events import create_audit_event
from app.services.meli.client import MercadoLibreClient
from app.services.meli.pictures import PictureUploadError, materialize_global_picture_sources
from app.services.meli.category_validation import validate_category_attributes
from app.services.meli.oauth import MercadoLibreOAuthClient
from app.services.meli.publisher import (
    SUPPORTED_LISTING_TYPE_IDS,
    execute_publish,
    reconcile_existing_publish,
    validate_delivery_binding,
    validate_publish_request,
    validate_store_delivery,
)
from app.services.meli.payload_builder import (
    build_cbt_global_item_payload,
    build_cbt_user_product_payload,
)
from app.services.meli.listing_type_validation import validate_store_category_listing_type
from app.services.meli.shipping import find_non_full_shipping_selection
from app.services.meli.token_vault import resolve_fresh_store_access_token
from app.services.publish_jobs import (
    cancel_publish_job,
    complete_publish_job,
    create_publish_job,
    list_publish_jobs,
    publish_blocking_errors,
    replay_publish_result,
    to_publish_job_read,
)
from app.services.reviews import (
    get_latest_behavioral_review,
    get_publish_review,
)

router = APIRouter(prefix="/api/publishing", tags=["publishing"])
settings = get_settings()
SERVER_LISTING_TYPE_IDS = sorted(SUPPORTED_LISTING_TYPE_IDS)


def create_oauth_client(db: Session) -> MercadoLibreOAuthClient:
    credentials = resolve_integration_credentials(db, settings)
    return MercadoLibreOAuthClient(
        client_id=credentials.meli_client_id,
        client_secret=credentials.meli_client_secret,
        redirect_uri=settings.meli_redirect_uri,
    )


class PublishPreviewRequest(BaseModel):
    draft: ProductDraftCreate
    review: ReviewResponse
    listing_choice: ListingChoice
    valid_listing_type_ids: list[str]
    human_approved: bool


class PublishExecuteRequest(PublishPreviewRequest):
    store_id: int
    product_draft_id: int | None = None


class PublishFromDraftPreviewRequest(BaseModel):
    product_draft_id: int
    review: ReviewResponse
    valid_listing_type_ids: list[str]
    human_approved: bool


class PublishFromDraftExecuteRequest(PublishFromDraftPreviewRequest):
    store_id: int


class CbtPublishPreview(BaseModel):
    allowed: bool
    errors: list[str] = []
    payload: dict | None = None


class CbtPublishExecuteRequest(BaseModel):
    product_draft_id: int
    acknowledge_publish: bool = False


def _meli_global_publish_error(exc: httpx.HTTPStatusError) -> str:
    """Return actionable marketplace validation feedback without exposing headers."""
    base = f"meli_global_publish_failed:{exc.response.status_code}"
    try:
        body = exc.response.json()
    except ValueError:
        return base
    if not isinstance(body, dict):
        return base

    parts = [
        str(body[key]).strip()
        for key in ("error", "message", "code")
        if isinstance(body.get(key), (str, int, float)) and str(body[key]).strip()
    ]
    causes = body.get("cause")
    if isinstance(causes, list):
        for cause in causes[:8]:
            if not isinstance(cause, dict):
                continue
            cause_parts = [
                str(cause[key]).strip()
                for key in ("code", "message")
                if isinstance(cause.get(key), (str, int, float)) and str(cause[key]).strip()
            ]
            if cause_parts:
                parts.append(" / ".join(cause_parts))
    if not parts:
        return base
    # API responses are untrusted external text. Keep a bounded field-level
    # validation summary rather than headers or a raw response body.
    return f"{base}: {' | '.join(parts)[:800]}"


def _global_response_item_identity(response: dict | list) -> tuple[str, str]:
    """Read the documented and observed Global Selling item-id response shapes."""
    candidates: list[dict] = []
    root_keys: list[str] = []
    if isinstance(response, dict):
        root_keys = sorted(str(key) for key in response.keys())[:20]
    elif isinstance(response, list):
        root_keys = ["array"]

    def collect(value: object, depth: int = 0) -> None:
        if depth > 4:
            return
        if isinstance(value, dict):
            candidates.append(value)
            # A CBT response may nest one result per marketplace under
            # site_items; follow response containers, never arbitrary text.
            for key in ("item", "global_item", "data", "items", "results", "site_items"):
                if key in value:
                    collect(value[key], depth + 1)
        elif isinstance(value, list):
            for item in value[:20]:
                collect(item, depth + 1)

    collect(response)
    for candidate in candidates:
        item_id = str(
            candidate.get("id")
            or candidate.get("item_id")
            or candidate.get("global_item_id")
            or ""
        ).strip()
        if item_id:
            return item_id, str(candidate.get("permalink") or response.get("permalink") or "").strip()
    # Do not expose raw responses. The bounded key list tells us which API
    # contract shape must be handled if Mercado Libre accepts without an id.
    return "", ",".join(root_keys)


def _global_response_details(response: dict | list) -> dict:
    """Keep only response fields needed to reconcile a Global Selling result."""
    if not isinstance(response, dict):
        return {"response_type": "array" if isinstance(response, list) else "unknown"}
    details = {
        key: response[key]
        for key in ("item_id", "seller_id", "site_id", "parent_user_product_id")
        if key in response
    }
    site_items = response.get("site_items")
    if isinstance(site_items, list):
        details["site_items"] = [
            {
                key: item[key]
                for key in ("item_id", "seller_id", "site_id", "logistic_type", "status", "error", "message")
                if key in item
            }
            for item in site_items[:12]
            if isinstance(item, dict)
        ]
    elif isinstance(site_items, dict):
        details["site_items"] = {
            str(site): (
                {
                    key: value[key]
                    for key in ("item_id", "seller_id", "site_id", "logistic_type", "status", "error", "message")
                    if key in value
                }
                if isinstance(value, dict)
                else str(value)[:300]
            )
            for site, value in list(site_items.items())[:12]
        }
    return details


def _classic_fallback_offers(response: dict | list, payload: dict) -> list[dict]:
    """Select only Premium site failures that Mercado Libre explicitly rejects.

    A Global Selling parent item may already exist while one marketplace rejects
    ``gold_pro``.  That site can safely be updated independently on the known
    parent using ``gold_special``; rate-limit and all other failures are never
    retried here.
    """
    if not isinstance(response, dict) or not isinstance(response.get("site_items"), list):
        return []
    offers = {
        str(offer.get("site_id", "")).upper(): offer
        for offer in payload.get("sites_to_sell", [])
        if isinstance(offer, dict)
    }
    fallbacks: list[dict] = []
    for row in response["site_items"]:
        if not isinstance(row, dict) or not isinstance(row.get("error"), dict):
            continue
        site_id = str(row.get("site_id", "")).upper()
        offer = offers.get(site_id)
        if not offer or str(offer.get("listing_type_id", "")).lower() != "gold_pro":
            continue
        error = row["error"]
        causes = error.get("cause")
        codes = {str(error.get("error") or error.get("code") or "").lower()}
        if isinstance(causes, list):
            codes.update(
                str(cause.get("code") or "").lower()
                for cause in causes
                if isinstance(cause, dict)
            )
        if "invalid.listing_type_id" not in codes:
            continue
        fallbacks.append({**offer, "listing_type_id": "gold_special"})
    return fallbacks


def _merge_global_site_items(original: dict | list, replacement: dict | list) -> dict | list:
    """Replace only the retried marketplace rows in a Global Selling response."""
    if not isinstance(original, dict) or not isinstance(replacement, dict):
        return original
    initial_rows = original.get("site_items")
    retry_rows = replacement.get("site_items")
    if not isinstance(initial_rows, list) or not isinstance(retry_rows, list):
        return original
    retry_by_site = {
        str(row.get("site_id", "")).upper(): row
        for row in retry_rows
        if isinstance(row, dict) and str(row.get("site_id", "")).strip()
    }
    merged_rows = [
        retry_by_site.get(str(row.get("site_id", "")).upper(), row)
        if isinstance(row, dict)
        else row
        for row in initial_rows
    ]
    known_sites = {
        str(row.get("site_id", "")).upper()
        for row in initial_rows
        if isinstance(row, dict)
    }
    merged_rows.extend(row for site, row in retry_by_site.items() if site not in known_sites)
    return {**original, "site_items": merged_rows}


def _record_classic_fallback(
    config: object,
    fallback_offers: list[dict],
) -> bool:
    """Persist an accepted Premium-to-Classic fallback for later editor loads."""
    fallback_sites = {str(offer.get("site_id", "")).upper() for offer in fallback_offers}
    if not fallback_sites or not hasattr(config, "sites_to_sell_json"):
        return False
    current = getattr(config, "sites_to_sell_json") or []
    updated = [
        {**offer, "listing_type_id": "gold_special"}
        if isinstance(offer, dict)
        and str(offer.get("site_id", "")).upper() in fallback_sites
        and str(offer.get("listing_type_id", "")).lower() == "gold_pro"
        else offer
        for offer in current
    ]
    if updated == current:
        return False
    config.sites_to_sell_json = updated
    config.updated_at = datetime.now(UTC)
    return True


def _global_response_site_errors(response: dict | list) -> list[str]:
    """Return deterministic per-site validation failures from a 200 response.

    Global Selling may return HTTP 200 with no parent item id when every
    requested marketplace rejected its own child listing. This is a known
    failure, not an unknown create outcome, and must not permanently block a
    corrected configuration from being submitted later.
    """
    if not isinstance(response, dict) or not isinstance(response.get("site_items"), list):
        return []
    rows = [item for item in response["site_items"] if isinstance(item, dict)]
    if not rows or any(not isinstance(item.get("error"), dict) for item in rows):
        return []
    errors: list[str] = []
    for item in rows[:12]:
        site_id = str(item.get("site_id") or "unknown_site").strip().upper()
        error = item["error"]
        causes = error.get("cause")
        if isinstance(causes, list) and causes:
            for cause in causes[:3]:
                if not isinstance(cause, dict):
                    continue
                code = str(cause.get("code") or "validation_error").strip()
                message = str(cause.get("message") or error.get("message") or "Validation error").strip()
                errors.append(f"{site_id}: {code} / {message}"[:800])
        else:
            errors.append(
                f"{site_id}: {str(error.get('error') or 'validation_error').strip()} / "
                f"{str(error.get('message') or 'Validation error').strip()}"[:800]
            )
    return list(dict.fromkeys(errors))


@router.post("/cbt/preview-from-draft", response_model=CbtPublishPreview)
def preview_cbt_publish_from_draft(
    product_draft_id: int,
    db: Session = Depends(get_db),
) -> CbtPublishPreview:
    config = get_cbt_listing_config(db, product_draft_id)
    draft = db.get(ProductDraft, product_draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Product draft not found.")
    store = db.get(Store, config.store_id)
    errors: list[str] = []
    if store is None or store.site_id.strip().upper() != "CBT" or store.oauth_status != "connected":
        errors.append("connected_cbt_store_required")
    resolved_attributes, attribute_errors = resolve_cbt_attribute_value_ids(
        db, config.category_id, config.attributes_json or []
    )
    errors.extend(attribute_errors)
    raw_config = {
        "store_id": config.store_id,
        "category_id": config.category_id,
        "family_name": config.family_name,
        "global_title": config.global_title,
        "description": config.description,
        "price_usd": config.price_usd,
        "available_quantity": config.available_quantity,
        "attributes": resolved_attributes,
        "sale_terms": config.sale_terms_json or [],
        "sites_to_sell": config.sites_to_sell_json or [],
    }
    try:
        payload = build_cbt_global_item_payload(
            ProductDraftCreate(
                title=draft.title,
                description=draft.description,
                brand=draft.brand,
                target_site_id="CBT",
                target_category_id=config.category_id,
                price=config.price_usd,
                currency="USD",
                stock=config.available_quantity,
                image_urls=draft.image_urls_json or [],
            ),
            CbtListingConfigUpsert.model_validate(raw_config),
        )
    except ValueError as exc:
        errors.append(str(exc))
        payload = None
    return CbtPublishPreview(allowed=not errors, errors=errors, payload=payload)


@router.post("/cbt/execute-from-draft", response_model=PublishExecutionResult)
async def execute_cbt_publish_from_draft(
    request: CbtPublishExecuteRequest,
    db: Session = Depends(get_db),
) -> PublishExecutionResult:
    """Create one traditional Global Selling item after configuration checks."""
    if not request.acknowledge_publish:
        return PublishExecutionResult(status="blocked", errors=["publish_acknowledgement_required"])
    if not settings.allow_live_publish:
        return PublishExecutionResult(status="blocked", errors=["live_publish_disabled"])

    config = get_cbt_listing_config(db, request.product_draft_id)
    draft = db.scalar(
        select(ProductDraft)
        .where(ProductDraft.id == request.product_draft_id)
        .with_for_update()
    )
    store = db.scalar(select(Store).where(Store.id == config.store_id).with_for_update())
    if draft is None:
        raise HTTPException(status_code=404, detail="Product draft not found.")
    if store is None:
        raise HTTPException(status_code=404, detail="Store not found.")
    if store.site_id.strip().upper() != "CBT" or store.oauth_status != "connected":
        return PublishExecutionResult(status="blocked", errors=["connected_cbt_store_required"])
    if config.draft_content_version != draft.content_version:
        return PublishExecutionResult(
            status="blocked", errors=["cbt_listing_config_stale_save_again_required"]
        )

    resolved_attributes, attribute_errors = resolve_cbt_attribute_value_ids(
        db, config.category_id, config.attributes_json or []
    )
    if attribute_errors:
        return PublishExecutionResult(status="blocked", errors=attribute_errors)
    if resolved_attributes != (config.attributes_json or []):
        before_attributes = config.attributes_json or []
        config.attributes_json = resolved_attributes
        config.updated_at = datetime.now(UTC)
        create_audit_event(
            db=db,
            actor_type="system",
            actor_id="cbt_attribute_resolver",
            action="cbt_listing_config.attribute_value_ids_resolved",
            entity_type="product_draft",
            entity_id=str(draft.id),
            before={"attributes": before_attributes},
            after={"attributes": resolved_attributes},
            commit=False,
        )
    raw_config = {
        "store_id": config.store_id,
        "category_id": config.category_id,
        "family_name": config.family_name,
        "global_title": config.global_title,
        "description": config.description,
        "price_usd": config.price_usd,
        "available_quantity": config.available_quantity,
        "attributes": resolved_attributes,
        "sale_terms": config.sale_terms_json or [],
        "sites_to_sell": config.sites_to_sell_json or [],
    }
    try:
        traditional_payload = build_cbt_global_item_payload(
            ProductDraftCreate(
                title=draft.title,
                description=draft.description,
                brand=draft.brand,
                target_site_id="CBT",
                target_category_id=config.category_id,
                price=config.price_usd,
                currency="USD",
                stock=config.available_quantity,
                image_urls=draft.image_urls_json or [],
            ),
            CbtListingConfigUpsert.model_validate(raw_config),
        )
    except ValueError as exc:
        return PublishExecutionResult(status="blocked", errors=[str(exc)])

    # Build the User Products (UP Siteless) variant of the same draft so the
    # publish worker can pick the correct model at execution time from the
    # seller's current tags. A strict build failure is recorded (not fatal) so
    # a traditional publish still works; UP accounts get a clear error instead.
    user_product_payload = None
    user_product_build_error = None
    try:
        user_product_payload = build_cbt_user_product_payload(
            ProductDraftCreate(
                title=draft.title,
                description=draft.description,
                brand=draft.brand,
                target_site_id="CBT",
                target_category_id=config.category_id,
                price=config.price_usd,
                currency="USD",
                stock=config.available_quantity,
                image_urls=draft.image_urls_json or [],
            ),
            CbtListingConfigUpsert.model_validate(raw_config),
        )
    except ValueError as exc:
        user_product_build_error = str(exc)

    idempotency_key = hashlib.sha256(
        json.dumps(
            {
                "model": "cbt_global_auto",
                "draft_id": draft.id,
                "draft_version": draft.content_version,
                "store_id": store.id,
                "payload": traditional_payload,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    if db.get_bind().dialect.name == "postgresql":
        db.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:lock_name))"),
            {"lock_name": f"publish_subject:{draft.id}:{store.id}"},
        )
        db.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:lock_name))"),
            {"lock_name": f"publish_job:{idempotency_key}"},
        )
    unresolved_job = None
    for candidate in (
        db.query(PublishJob)
        .filter(
            PublishJob.product_draft_id == draft.id,
            PublishJob.store_id == store.id,
            PublishJob.status.in_([PublishJobStatus.PENDING, PublishJobStatus.VALIDATING, PublishJobStatus.BLOCKED]),
        )
        .order_by(PublishJob.id.desc())
        .all()
    ):
        summary = candidate.response_summary_json or {}
        if candidate.status in {PublishJobStatus.PENDING, PublishJobStatus.VALIDATING}:
            unresolved_job = candidate
            break
        if "global_publish_outcome_unknown_manual_reconciliation_required" not in summary.get("errors", []):
            continue
        known_site_errors = _global_response_site_errors(summary.get("response_details", {}))
        if known_site_errors:
            # A legacy response was previously labeled unknown merely because
            # it lacked a parent item id. Every site supplied a validation
            # error, so it is safe to close this job as a known rejection.
            candidate.status = PublishJobStatus.FAILED
            candidate.response_summary_json = {
                **summary,
                "status": "failed",
                "errors": known_site_errors,
            }
            candidate.completed_at = candidate.completed_at or datetime.now(UTC)
            create_audit_event(
                db=db,
                actor_type="system",
                actor_id="cbt_response_reconciliation",
                action="cbt_global_publish.known_site_rejection_reconciled",
                entity_type="publish_job",
                entity_id=str(candidate.id),
                after={"status": "failed", "errors": known_site_errors},
                commit=False,
            )
            db.commit()
            continue
        unresolved_job = candidate
        break
    if unresolved_job is not None:
        return replay_publish_result(unresolved_job)
    job = db.query(PublishJob).filter(PublishJob.idempotency_key == idempotency_key).one_or_none()
    if job is not None:
        return replay_publish_result(job)
    job = PublishJob(
        product_draft_id=draft.id,
        store_id=store.id,
        requested_by="operator",
        idempotency_key=idempotency_key,
        status=PublishJobStatus.PENDING,
        started_at=None,
        request_summary_json={
            "publication_model": "auto",
            "draft_version": draft.content_version,
            "category_id": config.category_id,
            "marketplaces": [offer["site_id"] for offer in traditional_payload["sites_to_sell"]],
            "payload": traditional_payload,
            "user_product_payload": user_product_payload,
            "user_product_build_error": user_product_build_error,
        },
    )
    db.add(job)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.query(PublishJob).filter(PublishJob.idempotency_key == idempotency_key).one_or_none()
        if existing is None:
            raise
        return replay_publish_result(existing)
    db.refresh(job)

    return PublishExecutionResult(status="pending", job_id=job.id)


def _draft_latest_publish_status(db: Session, draft_ids: list[int]) -> dict[int, str]:
    """Map product draft id to the status of its most recent publish job."""
    if not draft_ids:
        return {}
    rows = (
        db.query(PublishJob.product_draft_id, PublishJob.status)
        .filter(PublishJob.product_draft_id.in_(draft_ids))
        .order_by(PublishJob.id.desc())
        .all()
    )
    result: dict[int, str] = {}
    for draft_id, status in rows:
        result.setdefault(draft_id, str(status))
    return result


def _queue_cbt_global_draft_job(
    db: Session,
    draft_id: int,
) -> tuple[PublishJob | None, str | None]:
    """Queue a CBT Global Selling publish job for one draft (worker path).

    Used by the family merge endpoint. Mirrors the core checks of
    execute_cbt_publish_from_draft and snapshots both the traditional and the
    User Products payload so the worker can pick the right model at execution
    time. An existing PENDING/VALIDATING job for the same draft is reused.
    """
    draft = db.query(ProductDraft).filter(ProductDraft.id == draft_id).one_or_none()
    if draft is None:
        return None, "product_draft_not_found"
    config = get_cbt_listing_config(db, draft_id)
    if config is None:
        return None, "cbt_listing_config_required"
    store = db.get(Store, config.store_id)
    if (
        store is None
        or store.site_id.strip().upper() != "CBT"
        or store.oauth_status != "connected"
    ):
        return None, "connected_cbt_store_required"
    if config.draft_content_version != draft.content_version:
        return None, "cbt_listing_config_stale_save_again_required"
    resolved_attributes, attribute_errors = resolve_cbt_attribute_value_ids(
        db, config.category_id, config.attributes_json or []
    )
    if attribute_errors:
        return None, attribute_errors[0]
    raw_config = {
        "store_id": config.store_id,
        "category_id": config.category_id,
        "family_name": config.family_name,
        "global_title": config.global_title,
        "description": config.description,
        "price_usd": config.price_usd,
        "available_quantity": config.available_quantity,
        "attributes": resolved_attributes,
        "sale_terms": config.sale_terms_json or [],
        "sites_to_sell": config.sites_to_sell_json or [],
    }
    draft_create = ProductDraftCreate(
        title=draft.title,
        description=draft.description,
        brand=draft.brand,
        target_site_id="CBT",
        target_category_id=config.category_id,
        price=config.price_usd,
        currency="USD",
        stock=config.available_quantity,
        image_urls=draft.image_urls_json or [],
    )
    config_model = CbtListingConfigUpsert.model_validate(raw_config)
    try:
        payload = build_cbt_global_item_payload(draft_create, config_model)
        user_product_payload = build_cbt_user_product_payload(draft_create, config_model)
    except ValueError as exc:
        return None, str(exc)
    existing = (
        db.query(PublishJob)
        .filter(
            PublishJob.product_draft_id == draft.id,
            PublishJob.status.in_([PublishJobStatus.PENDING, PublishJobStatus.VALIDATING]),
        )
        .order_by(PublishJob.id.desc())
        .first()
    )
    if existing is not None:
        return existing, None
    job = PublishJob(
        product_draft_id=draft.id,
        store_id=store.id,
        requested_by="operator",
        idempotency_key=hashlib.sha256(
            json.dumps(
                {
                    "model": "cbt_family_batch",
                    "draft_id": draft.id,
                    "payload": payload,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest(),
        status=PublishJobStatus.PENDING,
        started_at=None,
        request_summary_json={
            "publication_model": "auto",
            "draft_version": draft.content_version,
            "category_id": config.category_id,
            "marketplaces": [offer["site_id"] for offer in payload["sites_to_sell"]],
            "payload": payload,
            "user_product_payload": user_product_payload,
            "user_product_build_error": None,
        },
    )
    db.add(job)
    db.flush()
    return job, None


@router.get("/cbt/family-drafts/{draft_id}")
def list_cbt_family_drafts(
    draft_id: int,
    db: Session = Depends(get_db),
) -> dict:
    """Return sibling drafts sharing the same family_name and store."""
    config = get_cbt_listing_config(db, draft_id)
    if config is None:
        raise HTTPException(status_code=404, detail="CBT listing config not found.")
    rows = (
        db.query(CbtListingConfig, ProductDraft)
        .join(ProductDraft, ProductDraft.id == CbtListingConfig.product_draft_id)
        .filter(
            CbtListingConfig.family_name == config.family_name,
            CbtListingConfig.store_id == config.store_id,
        )
        .order_by(ProductDraft.id.asc())
        .all()
    )
    latest_status = _draft_latest_publish_status(
        db, [draft.id for _, draft in rows]
    )
    return {
        "family_name": config.family_name,
        "drafts": [
            {
                "product_draft_id": draft.id,
                "title": draft.title,
                "publication_status": latest_status.get(draft.id, "draft"),
                "variant_attributes": draft.source_variant_attributes_json or {},
                "price": draft.price,
            }
            for row, draft in rows
        ],
    }


class CbtFamilyPublishRequest(BaseModel):
    product_draft_ids: list[int]
    acknowledge_publish: bool = False


@router.post("/cbt/execute-from-drafts")
async def execute_cbt_family_publish(
    request: CbtFamilyPublishRequest,
    db: Session = Depends(get_db),
) -> dict:
    """Queue one publish job per draft; same family_name groups into one UP family.

    Under the User Products model all variations sharing the same family_name
    are grouped by Mercado Libre into a single product family (same
    siteless_family_id), so each job's UP can carry its own price/COLOR while
    the marketplace shows them as variants of one listing.
    """
    if not request.acknowledge_publish:
        return {"status": "blocked", "errors": ["publish_acknowledgement_required"]}
    if not settings.allow_live_publish:
        return {"status": "blocked", "errors": ["live_publish_disabled"]}
    if not request.product_draft_ids:
        return {"status": "blocked", "errors": ["cbt_family_publish_no_drafts"]}
    if len(request.product_draft_ids) > 30:
        return {"status": "blocked", "errors": ["cbt_family_publish_too_many_drafts"]}

    configs: list[tuple[int, CbtListingConfig]] = []
    for draft_id in request.product_draft_ids:
        config = get_cbt_listing_config(db, draft_id)
        if config is None:
            return {
                "status": "failed",
                "errors": [f"cbt_listing_config_required:draft_{draft_id}"],
            }
        configs.append((draft_id, config))

    stores = {config.store_id for _, config in configs}
    if len(stores) != 1:
        return {"status": "failed", "errors": ["cbt_family_mixed_stores"]}
    store = db.get(Store, next(iter(stores)))
    if (
        store is None
        or store.site_id.strip().upper() != "CBT"
        or store.oauth_status != "connected"
    ):
        return {"status": "blocked", "errors": ["connected_cbt_store_required"]}

    family_names = {config.family_name.strip() for _, config in configs}
    if len(family_names) != 1:
        return {
            "status": "failed",
            "errors": [
                "cbt_family_name_mismatch",
                "sibling_drafts_must_share_one_family_name",
            ],
        }

    jobs: list[dict] = []
    errors: list[str] = []
    for draft_id, _ in configs:
        job, error = _queue_cbt_global_draft_job(db, draft_id)
        if job is None:
            errors.append(f"draft_{draft_id}:{error}")
            continue
        jobs.append(
            {
                "product_draft_id": draft_id,
                "job_id": job.id,
                "status": "pending",
            }
        )
    db.commit()
    return {
        "status": "queued",
        "family_name": next(iter(family_names)),
        "queued_count": len(jobs),
        "jobs": jobs,
        "errors": errors,
    }


async def execute_cbt_global_publish_job(
    db: Session,
    job: PublishJob,
    token_encryption_key: str,
) -> PublishExecutionResult:
    """Execute a queued CBT Global Selling job (worker path).

    The endpoint queues the job with a full payload snapshot in
    request_summary_json; the publish worker claims PENDING jobs and runs this
    function to completion. complete_publish_job + audit are handled by the
    caller so the worker and any other caller stay consistent.
    """
    summary = job.request_summary_json or {}
    traditional_payload = summary.get("payload")
    user_product_payload = summary.get("user_product_payload")
    store = db.get(Store, job.store_id)
    draft = db.get(ProductDraft, job.product_draft_id)
    config = get_cbt_listing_config(db, job.product_draft_id)
    if traditional_payload is None or store is None or draft is None:
        return PublishExecutionResult(
            status="failed", errors=["cbt_publish_job_payload_missing"]
        )
    try:
        access_token = await resolve_fresh_store_access_token(
            db=db,
            store=store,
            encryption_key=token_encryption_key,
            oauth_client=create_oauth_client(db),
        )
        if not access_token:
            result = PublishExecutionResult(status="blocked", errors=["store_access_token_required"])
        else:
            client = MercadoLibreClient(access_token=access_token)
            user = await client.get("/users/me")
            user_data = user if isinstance(user, dict) else {}
            tags = user_data.get("tags", [])
            if str(user_data.get("site_id", "")).upper() != "CBT":
                result = PublishExecutionResult(
                    status="blocked", errors=["traditional_cbt_seller_required"]
                )
            else:
                is_up_seller = "user_product_seller" in tags
                publication_model = (
                    os.environ.get("CBT_PUBLICATION_MODEL", "auto").strip().lower()
                )
                if publication_model not in {"auto", "traditional", "user_product"}:
                    publication_model = "auto"
                use_up_model = (
                    publication_model == "user_product"
                    or (publication_model == "auto" and is_up_seller)
                )
                if use_up_model:
                    if not user_product_payload:
                        build_error = summary.get("user_product_build_error")
                        result = PublishExecutionResult(
                            status="failed",
                            errors=[
                                "cbt_user_product_payload_unavailable:"
                                + (str(build_error) if build_error else "missing_user_product_payload")
                            ],
                        )
                    else:
                        up_payload = await materialize_global_picture_sources(
                            client, user_product_payload
                        )
                        up_response = await client.post("/global/items", up_payload)
                        up_data = up_response if isinstance(up_response, (dict, list)) else {}
                        up_item_id, up_permalink_or_keys = _global_response_item_identity(up_data)
                        up_permalink = (
                            up_permalink_or_keys
                            if up_item_id
                            else str(up_data.get("permalink", "")).strip()
                            if isinstance(up_data, dict)
                            else ""
                        )
                        up_details = _global_response_details(up_data)
                        up_details["publication_model"] = "user_product"
                        if up_item_id:
                            result = PublishExecutionResult(
                                status="published",
                                item_id=up_item_id,
                                permalink=up_permalink,
                                response_details=up_details,
                            )
                        elif _global_response_site_errors(up_data):
                            result = PublishExecutionResult(
                                status="failed",
                                permalink=up_permalink,
                                response_details=up_details,
                                errors=_global_response_site_errors(up_data),
                            )
                        else:
                            result = PublishExecutionResult(
                                status="blocked",
                                permalink=up_permalink,
                                response_details=up_details,
                                errors=[
                                    "global_publish_outcome_unknown_manual_reconciliation_required",
                                    "meli_publish_response_missing_item_id",
                                    f"meli_global_response_keys:{up_permalink_or_keys or 'non_object'}",
                                ],
                            )
                else:
                    payload = traditional_payload
                    payload = await materialize_global_picture_sources(client, payload)
                    response = await client.post("/global/items", payload)
                    response_data = response if isinstance(response, (dict, list)) else {}
                    item_id, permalink_or_keys = _global_response_item_identity(response_data)
                    classic_fallbacks = _classic_fallback_offers(response_data, payload) if item_id else []
                    if classic_fallbacks:
                        try:
                            retry_response = await client.post(
                                f"/global/items/{item_id}", {"sites_to_sell": classic_fallbacks}
                            )
                        except httpx.HTTPStatusError as exc:
                            retry_response = {
                                "site_items": [
                                    {
                                        "site_id": offer["site_id"],
                                        "logistic_type": "remote",
                                        "error": {
                                            "error": "classic_fallback_failed",
                                            "message": _meli_global_publish_error(exc),
                                        },
                                    }
                                    for offer in classic_fallbacks
                                ]
                            }
                        response_data = _merge_global_site_items(response_data, retry_response)
                        if _record_classic_fallback(config, classic_fallbacks):
                            create_audit_event(
                                db=db,
                                actor_type="system",
                                actor_id="cbt_listing_type_fallback",
                                action="cbt_global_publish.premium_downgraded_to_classic",
                                entity_type="product_draft",
                                entity_id=str(job.product_draft_id),
                                after={
                                    "parent_item_id": item_id,
                                    "sites": [offer["site_id"] for offer in classic_fallbacks],
                                    "from_listing_type_id": "gold_pro",
                                    "to_listing_type_id": "gold_special",
                                },
                                commit=False,
                            )
                    permalink = (
                        permalink_or_keys
                        if item_id
                        else str(response_data.get("permalink", "")).strip()
                        if isinstance(response_data, dict)
                        else ""
                    )
                    response_details = _global_response_details(response_data)
                    response_details["publication_model"] = "traditional"
                    if classic_fallbacks:
                        response_details["listing_type_fallbacks"] = [
                            {"site_id": offer["site_id"], "from": "gold_pro", "to": "gold_special"}
                            for offer in classic_fallbacks
                        ]
                    result = (
                        PublishExecutionResult(
                            status="published",
                            item_id=item_id,
                            permalink=permalink,
                            response_details=response_details,
                        )
                        if item_id
                        else PublishExecutionResult(
                            status="failed",
                            permalink=permalink,
                            response_details=_global_response_details(response_data),
                            errors=_global_response_site_errors(response_data),
                        )
                        if _global_response_site_errors(response_data)
                        else PublishExecutionResult(
                            status="blocked",
                            permalink=permalink,
                            response_details=_global_response_details(response_data),
                            errors=[
                                "global_publish_outcome_unknown_manual_reconciliation_required",
                                "meli_publish_response_missing_item_id",
                                f"meli_global_response_keys:{permalink_or_keys or 'non_object'}",
                            ],
                        )
                    )
    except PictureUploadError as exc:
        result = PublishExecutionResult(status="failed", errors=[f"图片上传失败：{exc}"])
    except httpx.HTTPStatusError as exc:
        result = (
            PublishExecutionResult(
                status="blocked",
                errors=["global_publish_outcome_unknown_manual_reconciliation_required"],
            )
            if exc.response.status_code == 408 or exc.response.status_code >= 500
            else PublishExecutionResult(
                status="failed", errors=[_meli_global_publish_error(exc)]
            )
        )
    except Exception:
        result = PublishExecutionResult(
            status="blocked",
            errors=["global_publish_outcome_unknown_manual_reconciliation_required"],
        )
    return result


@dataclass(frozen=True)
class _PublishBatchCandidate:
    draft_id: int
    store_id: int
    draft: ProductDraftCreate
    review: ReviewResponse
    listing_choice: ListingChoice


@router.post("/preview", response_model=PublishValidationResult)
def publish_preview(
    payload: PublishPreviewRequest, db: Session = Depends(get_db)
) -> PublishValidationResult:
    validation = validate_publish_request(
        draft=payload.draft,
        review=payload.review,
        listing_choice=payload.listing_choice,
        valid_listing_type_ids=SERVER_LISTING_TYPE_IDS,
        human_approved=payload.human_approved,
    )
    store = db.get(Store, payload.listing_choice.store_id) if payload.listing_choice.store_id else None
    store_errors = (
        validate_store_delivery(
            store.id, store.site_id, store.oauth_status, payload.listing_choice
        )
        if store is not None
        else ["configured_store_not_found"]
    )
    listing_type_errors = (
        validate_store_category_listing_type(
            db,
            store.id,
            payload.draft.target_category_id,
            payload.listing_choice.listing_type_id,
            require_verified_metadata=True,
            max_age_seconds=settings.listing_type_cache_ttl_seconds,
        )
        if store is not None
        else []
    )
    errors = [*validation.errors, *store_errors, *listing_type_errors]
    if not errors and store is not None:
        errors.extend(_validate_current_store_shipping(db, store, payload.listing_choice))
    return validation.model_copy(update={"allowed": not errors, "errors": errors})


@router.post("/preview-from-draft", response_model=PublishValidationResult)
def publish_preview_from_draft(
    payload: PublishFromDraftPreviewRequest,
    db: Session = Depends(get_db),
) -> PublishValidationResult:
    draft, listing_choice = build_configured_draft(db, payload.product_draft_id)
    review = get_publish_review(
        db, payload.product_draft_id, payload.review.review_result_id
    )
    human_approved = is_product_draft_approved(db, payload.product_draft_id)
    validation = validate_publish_request(
        draft=draft,
        review=review,
        listing_choice=listing_choice,
        valid_listing_type_ids=SERVER_LISTING_TYPE_IDS,
        human_approved=human_approved,
    )
    validation = _with_category_attribute_validation(db, draft, listing_choice, validation)
    if validation.allowed and listing_choice.store_id is not None:
        store = db.get(Store, listing_choice.store_id)
        if store is not None:
            errors = _validate_current_store_shipping(db, store, listing_choice)
            validation = validation.model_copy(
                update={"allowed": not errors, "errors": errors}
            )
    return validation


@router.post("/execute", response_model=PublishExecutionResult)
async def publish_execute(
    payload: PublishExecuteRequest, db: Session = Depends(get_db)
) -> PublishExecutionResult:
    if not payload.product_draft_id:
        raise HTTPException(status_code=422, detail="persisted_draft_required")
    draft, listing_choice = build_configured_draft(db, payload.product_draft_id)
    review = get_publish_review(
        db, payload.product_draft_id, payload.review.review_result_id
    )
    human_approved = is_product_draft_approved(db, payload.product_draft_id)
    return await _execute_with_payload(
        db=db,
        store_id=payload.store_id,
        product_draft_id=payload.product_draft_id,
        draft=draft,
        review=review,
        listing_choice=listing_choice,
        valid_listing_type_ids=SERVER_LISTING_TYPE_IDS,
        human_approved=human_approved,
    )


@router.post("/execute-from-draft", response_model=PublishExecutionResult)
async def publish_execute_from_draft(
    payload: PublishFromDraftExecuteRequest, db: Session = Depends(get_db)
) -> PublishExecutionResult:
    draft, listing_choice = build_configured_draft(db, payload.product_draft_id)
    review = get_publish_review(
        db, payload.product_draft_id, payload.review.review_result_id
    )
    human_approved = is_product_draft_approved(db, payload.product_draft_id)
    return await _execute_with_payload(
        db=db,
        store_id=payload.store_id,
        product_draft_id=payload.product_draft_id,
        draft=draft,
        review=review,
        listing_choice=listing_choice,
        valid_listing_type_ids=SERVER_LISTING_TYPE_IDS,
        human_approved=human_approved,
    )


@router.post("/enqueue-from-draft", response_model=PublishJobRead)
def publish_enqueue_from_draft(
    payload: PublishFromDraftExecuteRequest, db: Session = Depends(get_db)
) -> PublishJobRead:
    store = db.get(Store, payload.store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found.")
    draft, listing_choice = build_configured_draft(db, payload.product_draft_id)
    review = get_publish_review(
        db, payload.product_draft_id, payload.review.review_result_id
    )
    human_approved = is_product_draft_approved(db, payload.product_draft_id)
    validation = validate_publish_request(
        draft=draft,
        review=review,
        listing_choice=listing_choice,
        valid_listing_type_ids=SERVER_LISTING_TYPE_IDS,
        human_approved=human_approved,
    )
    validation_errors = [
        *validation.errors,
        *validate_store_category_listing_type(
            db,
            store.id,
            draft.target_category_id,
            listing_choice.listing_type_id,
            require_verified_metadata=settings.allow_live_publish,
            max_age_seconds=settings.listing_type_cache_ttl_seconds,
        ),
        *validate_store_delivery(
            store.id, store.site_id, store.oauth_status, listing_choice
        ),
    ]
    validation_errors.extend(
        validate_category_attributes(
            db,
            draft.target_category_id,
            listing_choice.attributes,
            require_verified_metadata=settings.allow_live_publish,
        )
    )
    if not validation_errors:
        validation_errors.extend(_validate_current_store_shipping(db, store, listing_choice))
    if validation_errors:
        raise HTTPException(status_code=422, detail=validation_errors)
    job = create_publish_job(
        db=db,
        product_draft_id=payload.product_draft_id,
        store_id=payload.store_id,
        requested_by="operator",
        draft=draft,
        review=review,
        listing_choice=listing_choice,
        valid_listing_type_ids=SERVER_LISTING_TYPE_IDS,
    )
    _audit_publish_request(
        db=db,
        action=(
            "publish.queue_replayed"
            if getattr(job, "_idempotent_replay", False)
            else "publish.queued"
        ),
        job=job,
        listing_choice=listing_choice,
    )
    return to_publish_job_read(job)


@router.post("/enqueue-batch", response_model=PublishBatchEnqueueResult)
def publish_enqueue_batch(
    payload: PublishBatchEnqueueRequest,
    db: Session = Depends(get_db),
) -> PublishBatchEnqueueResult:
    if not payload.acknowledge_publish:
        raise HTTPException(
            status_code=422,
            detail="publish_acknowledgement_required",
        )

    draft_ids = list(dict.fromkeys(payload.draft_ids))
    batch_id = uuid4().hex
    preflight_by_draft_id, candidates = _evaluate_publish_batch(db, draft_ids)
    item_by_draft_id = {
        draft_id: PublishBatchItem(
            draft_id=draft_id,
            outcome=item.outcome,
            errors=item.errors,
        )
        for draft_id, item in preflight_by_draft_id.items()
        if item.outcome != "ready"
    }

    for candidate in candidates:
        job = create_publish_job(
            db=db,
            product_draft_id=candidate.draft_id,
            store_id=candidate.store_id,
            requested_by="operator",
            draft=candidate.draft,
            review=candidate.review,
            listing_choice=candidate.listing_choice,
            valid_listing_type_ids=SERVER_LISTING_TYPE_IDS,
            commit=False,
        )
        replayed = bool(getattr(job, "_idempotent_replay", False))
        _audit_publish_request(
            db=db,
            action="publish.queue_replayed" if replayed else "publish.queued",
            job=job,
            listing_choice=candidate.listing_choice,
            commit=False,
        )
        item_by_draft_id[candidate.draft_id] = PublishBatchItem(
            draft_id=candidate.draft_id,
            outcome="existing" if replayed else "queued",
            job=to_publish_job_read(job),
        )

    items = [item_by_draft_id[draft_id] for draft_id in draft_ids]
    create_audit_event(
        db=db,
        actor_type="operator",
        actor_id="operator",
        action="publish.batch.queued",
        entity_type="publish_batch",
        entity_id=batch_id,
        after={
            "draft_ids": draft_ids,
            "queued_count": sum(item.outcome == "queued" for item in items),
            "existing_count": sum(item.outcome == "existing" for item in items),
            "not_ready_count": sum(item.outcome == "not_ready" for item in items),
            "not_found_count": sum(item.outcome == "not_found" for item in items),
        },
        commit=False,
    )
    db.commit()
    return PublishBatchEnqueueResult(
        batch_id=batch_id,
        queued_count=sum(item.outcome == "queued" for item in items),
        existing_count=sum(item.outcome == "existing" for item in items),
        not_ready_count=sum(item.outcome == "not_ready" for item in items),
        not_found_count=sum(item.outcome == "not_found" for item in items),
        items=items,
    )


@router.post("/preflight-batch", response_model=PublishBatchPreflightResult)
def publish_preflight_batch(
    payload: PublishBatchPreflightRequest,
    db: Session = Depends(get_db),
) -> PublishBatchPreflightResult:
    draft_ids = list(dict.fromkeys(payload.draft_ids))
    item_by_draft_id, _ = _evaluate_publish_batch(db, draft_ids)
    items = [item_by_draft_id[draft_id] for draft_id in draft_ids]
    return PublishBatchPreflightResult(
        ready_count=sum(item.outcome == "ready" for item in items),
        not_ready_count=sum(item.outcome == "not_ready" for item in items),
        not_found_count=sum(item.outcome == "not_found" for item in items),
        items=items,
    )


def _evaluate_publish_batch(
    db: Session,
    draft_ids: list[int],
) -> tuple[dict[int, PublishBatchPreflightItem], list[_PublishBatchCandidate]]:
    item_by_draft_id: dict[int, PublishBatchPreflightItem] = {}
    candidates: list[_PublishBatchCandidate] = []
    shipping_errors_by_selection: dict[tuple[int, str, str], list[str]] = {}

    for draft_id in draft_ids:
        model = db.get(ProductDraft, draft_id)
        if model is None:
            item_by_draft_id[draft_id] = PublishBatchPreflightItem(
                draft_id=draft_id,
                outcome="not_found",
                errors=["product_draft_not_found"],
            )
            continue
        try:
            draft, listing_choice = build_configured_draft(db, draft_id)
            latest_review = get_latest_behavioral_review(db, model)
            review = get_publish_review(
                db,
                draft_id,
                latest_review.id if latest_review is not None else None,
            )
            human_approved = is_product_draft_approved(db, draft_id)
        except HTTPException as exc:
            item_by_draft_id[draft_id] = PublishBatchPreflightItem(
                draft_id=draft_id,
                outcome="not_ready",
                errors=publish_blocking_errors(exc.detail),
            )
            continue

        store = db.get(Store, listing_choice.store_id) if listing_choice.store_id else None
        if store is None:
            item_by_draft_id[draft_id] = PublishBatchPreflightItem(
                draft_id=draft_id,
                outcome="not_ready",
                errors=["configured_store_not_found"],
            )
            continue

        validation = validate_publish_request(
            draft=draft,
            review=review,
            listing_choice=listing_choice,
            valid_listing_type_ids=SERVER_LISTING_TYPE_IDS,
            human_approved=human_approved,
        )
        errors = [
            *validation.errors,
            *validate_store_category_listing_type(
                db,
                store.id,
                draft.target_category_id,
                listing_choice.listing_type_id,
                require_verified_metadata=settings.allow_live_publish,
                max_age_seconds=settings.listing_type_cache_ttl_seconds,
            ),
            *validate_store_delivery(
                store.id,
                store.site_id,
                store.oauth_status,
                listing_choice,
            ),
            *validate_category_attributes(
                db,
                draft.target_category_id,
                listing_choice.attributes,
                require_verified_metadata=settings.allow_live_publish,
            ),
        ]
        shipping_key = (
            store.id,
            listing_choice.shipping_mode,
            listing_choice.shipping_logistic_type,
        )
        if not errors:
            if shipping_key not in shipping_errors_by_selection:
                shipping_errors_by_selection[shipping_key] = _validate_current_store_shipping(
                    db,
                    store,
                    listing_choice,
                )
            errors.extend(shipping_errors_by_selection[shipping_key])
        if errors:
            item_by_draft_id[draft_id] = PublishBatchPreflightItem(
                draft_id=draft_id,
                outcome="not_ready",
                errors=errors,
            )
            continue

        item_by_draft_id[draft_id] = PublishBatchPreflightItem(
            draft_id=draft_id,
            outcome="ready",
        )
        candidates.append(
            _PublishBatchCandidate(
                draft_id=draft_id,
                store_id=store.id,
                draft=draft,
                review=review,
                listing_choice=listing_choice,
            )
        )

    return item_by_draft_id, candidates


def _validate_current_store_shipping(
    db: Session,
    store: Store,
    listing_choice: ListingChoice,
) -> list[str]:
    store_errors = validate_store_delivery(
        store.id,
        store.site_id,
        store.oauth_status,
        listing_choice,
    )
    if store_errors:
        return store_errors
    seller_id = store.seller_id
    try:
        access_token = asyncio.run(
            resolve_fresh_store_access_token(
                db=db,
                store=store,
                encryption_key=settings.token_encryption_key,
                oauth_client=create_oauth_client(db),
            )
        )
    except httpx.HTTPError:
        db.rollback()
        return ["store_token_refresh_unavailable"]
    except ValueError:
        db.rollback()
        return ["store_token_refresh_response_invalid"]
    if not access_token:
        db.rollback()
        return ["store_access_token_required"]

    # Release the read transaction before waiting on the external provider.
    db.rollback()
    try:
        preferences = asyncio.run(
            MercadoLibreClient(access_token=access_token).get(
                f"/users/{seller_id}/shipping_preferences"
            )
        )
    except httpx.HTTPError:
        return ["shipping_preferences_unavailable"]

    selected_available = find_non_full_shipping_selection(
        preferences,
        listing_choice.shipping_mode,
        listing_choice.shipping_logistic_type,
    )
    return [] if selected_available else ["selected_non_full_shipping_option_unavailable"]


@router.post("/jobs/{job_id}/retry", response_model=PublishExecutionResult)
async def retry_publish_job(job_id: int, db: Session = Depends(get_db)) -> PublishExecutionResult:
    job = db.scalar(select(PublishJob).where(PublishJob.id == job_id).with_for_update())
    if job is None:
        raise HTTPException(status_code=404, detail="Publish job not found.")
    if job.status not in {PublishJobStatus.BLOCKED, PublishJobStatus.FAILED}:
        raise HTTPException(
            status_code=400,
            detail="Only blocked or failed publish jobs can be retried.",
        )
    if job.meli_item_id:
        raise HTTPException(
            status_code=409,
            detail="Publish job already created an item; inspect it before another attempt.",
        )
    if "publish_outcome_unknown_manual_reconciliation_required" in (
        job.response_summary_json or {}
    ).get("errors", []):
        raise HTTPException(
            status_code=409,
            detail="Publish outcome is unknown; reconcile the store before another attempt.",
        )

    draft, listing_choice = build_configured_draft(db, job.product_draft_id)
    review = get_publish_review(
        db,
        job.product_draft_id,
        (job.request_summary_json or {}).get("review_result_id"),
    )
    human_approved = is_product_draft_approved(db, job.product_draft_id)
    previous_status = job.status
    job.status = PublishJobStatus.VALIDATING
    job.started_at = datetime.now(UTC)
    job.completed_at = None
    db.commit()
    db.refresh(job)
    create_audit_event(
        db=db,
        actor_type="operator",
        actor_id="operator",
        action="publish.retry_requested",
        entity_type="publish_job",
        entity_id=str(job.id),
        before={
            "status": (
                previous_status.value if hasattr(previous_status, "value") else str(previous_status)
            ),
            "product_draft_id": job.product_draft_id,
            "store_id": job.store_id,
        },
        after={
            "retry_product_draft_id": job.product_draft_id,
            "retry_store_id": job.store_id,
            "listing_type_id": listing_choice.listing_type_id,
            "shipping_mode": listing_choice.shipping_mode,
            "shipping_logistic_type": listing_choice.shipping_logistic_type,
        },
    )
    return await _execute_with_payload(
        db=db,
        store_id=job.store_id,
        product_draft_id=job.product_draft_id,
        draft=draft,
        review=review,
        listing_choice=listing_choice,
        valid_listing_type_ids=SERVER_LISTING_TYPE_IDS,
        human_approved=human_approved,
        execution_job=job,
    )


async def _execute_with_payload(
    db: Session,
    store_id: int,
    product_draft_id: int,
    draft: ProductDraftCreate,
    review: ReviewResponse,
    listing_choice: ListingChoice,
    valid_listing_type_ids: list[str],
    human_approved: bool,
    execution_job: PublishJob | None = None,
) -> PublishExecutionResult:
    store = db.get(Store, store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found.")
    job = execution_job or create_publish_job(
        db=db,
        product_draft_id=product_draft_id,
        store_id=store_id,
        requested_by="operator",
        draft=draft,
        review=review,
        listing_choice=listing_choice,
        valid_listing_type_ids=valid_listing_type_ids,
        initial_status=PublishJobStatus.VALIDATING,
    )
    if execution_job is None and getattr(job, "_idempotent_replay", False):
        _audit_publish_request(
            db=db,
            action="publish.idempotent_replay",
            job=job,
            listing_choice=listing_choice,
        )
        return replay_publish_result(job)

    validation = validate_publish_request(
        draft=draft,
        review=review,
        listing_choice=listing_choice,
        valid_listing_type_ids=valid_listing_type_ids,
        human_approved=human_approved,
    )
    validation_errors = [
        *validation.errors,
        *validate_store_category_listing_type(
            db,
            store.id,
            draft.target_category_id,
            listing_choice.listing_type_id,
            require_verified_metadata=settings.allow_live_publish,
            max_age_seconds=settings.listing_type_cache_ttl_seconds,
        ),
        *validate_store_delivery(
            store.id, store.site_id, store.oauth_status, listing_choice
        ),
        *validate_category_attributes(
            db,
            draft.target_category_id,
            listing_choice.attributes,
            require_verified_metadata=settings.allow_live_publish,
        ),
    ]
    validation = validation.model_copy(
        update={"allowed": not validation_errors, "errors": validation_errors}
    )
    if not validation.allowed:
        result = PublishExecutionResult(status="blocked", errors=validation.errors)
        complete_publish_job(db, job, result)
        _audit_publish_execution(
            db=db,
            job_id=job.id,
            product_draft_id=product_draft_id,
            store_id=store_id,
            listing_choice=listing_choice,
            human_approved=human_approved,
            result=result,
        )
        return result.model_copy(update={"job_id": job.id})
    access_token = await resolve_fresh_store_access_token(
        db=db,
        store=store,
        encryption_key=settings.token_encryption_key,
        oauth_client=create_oauth_client(db),
    )
    if not access_token:
        result = PublishExecutionResult(status="blocked", errors=["store_access_token_required"])
        complete_publish_job(db, job, result)
        _audit_publish_execution(
            db=db,
            job_id=job.id,
            product_draft_id=product_draft_id,
            store_id=store_id,
            listing_choice=listing_choice,
            human_approved=human_approved,
            result=result,
        )
        return result.model_copy(update={"job_id": job.id})
    try:
        draft, listing_choice = build_configured_draft(
            db, product_draft_id, lock_draft=True
        )
        review = get_publish_review(db, product_draft_id, review.review_result_id)
        human_approved = is_product_draft_approved(db, product_draft_id)
        store = db.scalar(
            select(Store)
            .where(Store.id == store_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if store is None:
            raise HTTPException(status_code=404, detail="Store not found.")
    except HTTPException as exc:
        result = PublishExecutionResult(
            status="blocked", errors=publish_blocking_errors(exc.detail)
        )
        complete_publish_job(db, job, result)
        _audit_publish_execution(
            db=db,
            job_id=job.id,
            product_draft_id=product_draft_id,
            store_id=store_id,
            listing_choice=listing_choice,
            human_approved=human_approved,
            result=result,
        )
        return result.model_copy(update={"job_id": job.id})
    final_validation = validate_publish_request(
        draft=draft,
        review=review,
        listing_choice=listing_choice,
        valid_listing_type_ids=valid_listing_type_ids,
        human_approved=human_approved,
    )
    final_errors = [
        *final_validation.errors,
        *validate_store_category_listing_type(
            db,
            store.id,
            draft.target_category_id,
            listing_choice.listing_type_id,
            require_verified_metadata=settings.allow_live_publish,
            max_age_seconds=settings.listing_type_cache_ttl_seconds,
        ),
        *validate_store_delivery(
            store.id, store.site_id, store.oauth_status, listing_choice
        ),
        *validate_category_attributes(
            db,
            draft.target_category_id,
            listing_choice.attributes,
            require_verified_metadata=settings.allow_live_publish,
        ),
    ]
    if final_errors:
        result = PublishExecutionResult(status="blocked", errors=final_errors)
        complete_publish_job(db, job, result)
        _audit_publish_execution(
            db=db,
            job_id=job.id,
            product_draft_id=product_draft_id,
            store_id=store_id,
            listing_choice=listing_choice,
            human_approved=human_approved,
            result=result,
        )
        return result.model_copy(update={"job_id": job.id})
    publish_reference = str(
        (job.request_summary_json or {}).get("publish_reference", "")
    ).strip()
    if not publish_reference:
        result = PublishExecutionResult(
            status="blocked", errors=["publish_reference_required"]
        )
    else:
        try:
            result = await execute_publish(
                client=MercadoLibreClient(access_token=access_token),
                seller_id=store.seller_id,
                draft=draft,
                review=review,
                listing_choice=listing_choice,
                valid_listing_type_ids=valid_listing_type_ids,
                human_approved=human_approved,
                allow_live_publish=settings.allow_live_publish,
                publish_reference=publish_reference,
            )
        except Exception:
            result = PublishExecutionResult(
                status="blocked",
                errors=["publish_outcome_unknown_manual_reconciliation_required"],
            )
    complete_publish_job(db, job, result)
    _audit_publish_execution(
        db=db,
        job_id=job.id,
        product_draft_id=product_draft_id,
        store_id=store_id,
        listing_choice=listing_choice,
        human_approved=human_approved,
        result=result,
    )
    return result.model_copy(update={"job_id": job.id})


@router.post("/jobs/{job_id}/cancel", response_model=PublishJobRead)
def cancel_pending_publish_job(
    job_id: int,
    db: Session = Depends(get_db),
) -> PublishJobRead:
    return to_publish_job_read(
        cancel_publish_job(db, job_id, cancelled_by="operator")
    )


@router.post("/jobs/{job_id}/reconcile", response_model=PublishExecutionResult)
async def reconcile_unknown_publish_job(
    job_id: int,
    db: Session = Depends(get_db),
) -> PublishExecutionResult:
    job = db.scalar(
        select(PublishJob)
        .where(PublishJob.id == job_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if job is None:
        raise HTTPException(status_code=404, detail="Publish job not found.")
    summary = job.request_summary_json or {}
    prior_errors = (job.response_summary_json or {}).get("errors", [])
    if (
        job.status != PublishJobStatus.BLOCKED
        or "publish_outcome_unknown_manual_reconciliation_required" not in prior_errors
    ):
        raise HTTPException(
            status_code=409,
            detail="Only an unresolved publish outcome can be reconciled.",
        )
    publish_reference = str(summary.get("publish_reference", "")).strip()
    if not publish_reference:
        raise HTTPException(
            status_code=409,
            detail="Publish job predates searchable reconciliation references.",
        )
    store = db.get(Store, job.store_id)
    if store is None:
        raise HTTPException(status_code=404, detail="Store not found.")
    reconciliation_lease = uuid4().hex
    job.status = PublishJobStatus.VALIDATING
    job.started_at = datetime.now(UTC)
    job.completed_at = None
    job.response_summary_json = {
        **(job.response_summary_json or {}),
        "status": PublishJobStatus.VALIDATING.value,
        "errors": ["publish_outcome_unknown_manual_reconciliation_required"],
        "reconciliation_lease": reconciliation_lease,
    }
    db.commit()

    result: PublishExecutionResult
    match_count = 0
    locked_job: PublishJob | None = None
    try:
        access_token = await resolve_fresh_store_access_token(
            db=db,
            store=store,
            encryption_key=settings.token_encryption_key,
            oauth_client=create_oauth_client(db),
        )
        if not access_token:
            result = PublishExecutionResult(
                status="blocked",
                errors=[
                    "publish_outcome_unknown_manual_reconciliation_required",
                    "store_access_token_required",
                ],
            )
        else:
            client = MercadoLibreClient(access_token=access_token)
            if job.meli_item_id:
                matches = [job.meli_item_id]
                match_count = 1
            else:
                search = await client.get(
                    f"/users/{store.seller_id}/items/search?sku="
                    f"{quote(publish_reference, safe='')}"
                )
                if not isinstance(search, dict):
                    raise ValueError("Mercado Libre search response is not an object.")
                raw_results = search.get("results")
                paging = search.get("paging")
                total = paging.get("total") if isinstance(paging, dict) else None
                if (
                    not isinstance(raw_results, list)
                    or not isinstance(total, int)
                    or total < 0
                ):
                    raise ValueError("Mercado Libre search total is unavailable.")
                matches = [
                    str(value).strip()
                    for value in raw_results
                    if str(value).strip()
                ]
                match_count = total
                if total != len(matches) or len(set(matches)) != len(matches):
                    if total > 1:
                        matches = []
                    else:
                        raise ValueError("Mercado Libre search page is inconsistent.")
            if match_count == 0:
                result = PublishExecutionResult(
                    status="blocked",
                    errors=[
                        "publish_outcome_unknown_manual_reconciliation_required",
                        "publish_reconciliation_no_match",
                    ],
                )
            elif match_count > 1:
                result = PublishExecutionResult(
                    status="blocked",
                    errors=[
                        "publish_outcome_unknown_manual_reconciliation_required",
                        "publish_reconciliation_multiple_matches",
                    ],
                )
            else:
                item = await client.get(f"/items/{quote(matches[0], safe='')}")
                if not isinstance(item, dict):
                    raise httpx.ResponseError("Mercado Libre item response is not an object.")
                locked_job = db.scalar(
                    select(PublishJob)
                    .where(PublishJob.id == job_id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
                if (
                    locked_job is None
                    or locked_job.status != PublishJobStatus.VALIDATING
                    or (locked_job.response_summary_json or {}).get(
                        "reconciliation_lease"
                    )
                    != reconciliation_lease
                ):
                    db.rollback()
                    raise HTTPException(
                        status_code=409,
                        detail="Publish reconciliation was superseded by a newer attempt.",
                    )
                result = await reconcile_existing_publish(
                    client,
                    item,
                    seller_id=store.seller_id,
                    publish_reference=publish_reference,
                    site_id=str(summary.get("site_id", "")),
                    category_id=str(summary.get("category_id", "")),
                    listing_type_id=str(summary.get("listing_type_id", "")),
                    expected_shipping_mode=str(summary.get("shipping_mode", "")),
                    expected_shipping_logistic_type=str(
                        summary.get("shipping_logistic_type", "")
                    ),
                    expected_item_id=matches[0],
                    description=str(summary.get("description", "")),
                )
    except (httpx.HTTPError, ValueError):
        result = PublishExecutionResult(
            status="blocked",
            errors=[
                "publish_outcome_unknown_manual_reconciliation_required",
                "publish_reconciliation_unavailable",
            ],
        )

    current_job = locked_job or db.scalar(
        select(PublishJob)
        .where(PublishJob.id == job_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if (
        current_job is None
        or current_job.status != PublishJobStatus.VALIDATING
        or (current_job.response_summary_json or {}).get("reconciliation_lease")
        != reconciliation_lease
    ):
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Publish reconciliation was superseded by a newer attempt.",
        )
    job = current_job
    if "meli_publish_item_id_mismatch" in result.errors:
        job.meli_item_id = ""
        job.permalink = ""
    complete_publish_job(db, job, result)
    create_audit_event(
        db=db,
        actor_type="operator",
        actor_id="operator",
        action="publish.reconciled",
        entity_type="publish_job",
        entity_id=str(job.id),
        before={"status": PublishJobStatus.BLOCKED.value},
        after={
            "status": result.status,
            "item_id": result.item_id,
            "match_count": match_count,
            "errors": result.errors,
        },
    )
    return result.model_copy(update={"job_id": job.id})


def _with_category_attribute_validation(
    db: Session,
    draft: ProductDraftCreate,
    listing_choice: ListingChoice,
    validation: PublishValidationResult,
) -> PublishValidationResult:
    store = db.get(Store, listing_choice.store_id) if listing_choice.store_id else None
    store_errors = (
        ["configured_store_not_found"]
        if store is None and listing_choice.store_id is not None
        else (
            validate_store_delivery(
                store.id, store.site_id, store.oauth_status, listing_choice
            )
            if store is not None
            else validate_delivery_binding(None, listing_choice)
        )
    )
    errors = [
        *validation.errors,
        *store_errors,
        *(
            validate_store_category_listing_type(
                db,
                store.id,
                draft.target_category_id,
                listing_choice.listing_type_id,
                require_verified_metadata=True,
                max_age_seconds=settings.listing_type_cache_ttl_seconds,
            )
            if store is not None
            else []
        ),
        *validate_category_attributes(
            db,
            draft.target_category_id,
            listing_choice.attributes,
            require_verified_metadata=settings.allow_live_publish,
        ),
    ]
    return validation.model_copy(update={"allowed": not errors, "errors": errors})


def _audit_publish_execution(
    db: Session,
    job_id: int,
    product_draft_id: int,
    store_id: int,
    listing_choice: ListingChoice,
    human_approved: bool,
    result: PublishExecutionResult,
) -> None:
    create_audit_event(
        db=db,
        actor_type="operator",
        actor_id="operator",
        action="publish.executed",
        entity_type="publish_job",
        entity_id=str(job_id),
        before={
            "product_draft_id": product_draft_id,
            "store_id": store_id,
            "listing_type_id": listing_choice.listing_type_id,
            "shipping_mode": listing_choice.shipping_mode,
            "shipping_logistic_type": listing_choice.shipping_logistic_type,
            "human_approved": human_approved,
        },
        after={
            "status": result.status,
            "item_id": result.item_id,
            "permalink": result.permalink,
            "shipping_mode": result.shipping_mode,
            "shipping_logistic_type": result.shipping_logistic_type,
            "errors": result.errors,
            "store_id": store_id,
        },
    )


def _audit_publish_request(
    db: Session,
    action: str,
    job: PublishJob,
    listing_choice: ListingChoice,
    commit: bool = True,
) -> None:
    create_audit_event(
        db=db,
        actor_type="operator",
        actor_id="operator",
        action=action,
        entity_type="publish_job",
        entity_id=str(job.id),
        before={},
        after={
            "product_draft_id": job.product_draft_id,
            "store_id": job.store_id,
            "site_id": listing_choice.site_id,
            "listing_type_id": listing_choice.listing_type_id,
            "shipping_mode": listing_choice.shipping_mode,
            "shipping_logistic_type": listing_choice.shipping_logistic_type,
        },
        commit=commit,
    )


@router.get("/jobs", response_model=list[PublishJobRead])
def get_publish_jobs(
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[PublishJobRead]:
    return list_publish_jobs(db, limit=limit, offset=offset)
