import asyncio
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
from app.services.draft_approvals import (
    get_product_draft_approval,
    is_product_draft_approved,
)
from app.services.draft_listing_configs import build_configured_draft
from app.services.cbt_listing_configs import get_cbt_listing_config
from app.services.integration_credentials import resolve_integration_credentials
from app.services.audit_events import create_audit_event
from app.services.meli.client import MercadoLibreClient
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
from app.services.meli.payload_builder import build_cbt_global_item_payload
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
    provider_review_context_errors,
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
    raw_config = {
        "store_id": config.store_id,
        "category_id": config.category_id,
        "family_name": config.family_name,
        "global_title": config.global_title,
        "description": config.description,
        "price_usd": config.price_usd,
        "available_quantity": config.available_quantity,
        "attributes": config.attributes_json or [],
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

    raw_config = {
        "store_id": config.store_id,
        "category_id": config.category_id,
        "family_name": config.family_name,
        "global_title": config.global_title,
        "description": config.description,
        "price_usd": config.price_usd,
        "available_quantity": config.available_quantity,
        "attributes": config.attributes_json or [],
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
        return PublishExecutionResult(status="blocked", errors=[str(exc)])

    idempotency_key = hashlib.sha256(
        json.dumps(
            {
                "model": "traditional_global",
                "draft_id": draft.id,
                "draft_version": draft.content_version,
                "store_id": store.id,
                "payload": payload,
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
    unresolved_job = next(
        (
            candidate
            for candidate in db.query(PublishJob)
            .filter(
                PublishJob.product_draft_id == draft.id,
                PublishJob.store_id == store.id,
                PublishJob.status.in_([PublishJobStatus.PENDING, PublishJobStatus.VALIDATING, PublishJobStatus.BLOCKED]),
            )
            .order_by(PublishJob.id.desc())
            .all()
            if candidate.status in {PublishJobStatus.PENDING, PublishJobStatus.VALIDATING}
            or "global_publish_outcome_unknown_manual_reconciliation_required"
            in (candidate.response_summary_json or {}).get("errors", [])
        ),
        None,
    )
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
        status=PublishJobStatus.VALIDATING,
        started_at=datetime.now(UTC),
        request_summary_json={
            "publication_model": "traditional_global",
            "draft_version": draft.content_version,
            "category_id": config.category_id,
            "marketplaces": [offer["site_id"] for offer in payload["sites_to_sell"]],
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

    try:
        access_token = await resolve_fresh_store_access_token(
            db=db,
            store=store,
            encryption_key=settings.token_encryption_key,
            oauth_client=create_oauth_client(db),
        )
        if not access_token:
            result = PublishExecutionResult(status="blocked", errors=["store_access_token_required"])
        else:
            client = MercadoLibreClient(access_token=access_token)
            user = await client.get("/users/me")
            user_data = user if isinstance(user, dict) else {}
            tags = user_data.get("tags", [])
            if (
                str(user_data.get("site_id", "")).upper() != "CBT"
                or "user_products_seller" in tags
            ):
                result = PublishExecutionResult(
                    status="blocked", errors=["traditional_cbt_seller_required"]
                )
            else:
                response = await client.post("/global/items", payload)
                response_data = response if isinstance(response, dict) else {}
                item_id = str(response_data.get("id", "")).strip()
                permalink = str(response_data.get("permalink", "")).strip()
                result = (
                    PublishExecutionResult(status="published", item_id=item_id, permalink=permalink)
                    if item_id
                    else PublishExecutionResult(
                        status="blocked",
                        permalink=permalink,
                        errors=[
                            "global_publish_outcome_unknown_manual_reconciliation_required",
                            "meli_publish_response_missing_item_id",
                        ],
                    )
                )
    except httpx.HTTPStatusError as exc:
        result = (
            PublishExecutionResult(
                status="blocked",
                errors=["global_publish_outcome_unknown_manual_reconciliation_required"],
            )
            if exc.response.status_code == 408 or exc.response.status_code >= 500
            else PublishExecutionResult(
                status="failed", errors=[f"meli_global_publish_failed:{exc.response.status_code}"]
            )
        )
    except Exception:
        result = PublishExecutionResult(
            status="blocked",
            errors=["global_publish_outcome_unknown_manual_reconciliation_required"],
        )

    complete_publish_job(db, job, result)
    create_audit_event(
        db=db,
        actor_type="operator",
        actor_id="operator",
        action="cbt_global_publish.executed",
        entity_type="publish_job",
        entity_id=str(job.id),
        after={
            "product_draft_id": draft.id,
            "store_id": store.id,
            "status": result.status,
            "item_id": result.item_id,
            "errors": result.errors,
        },
    )
    return result.model_copy(update={"job_id": job.id})


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
