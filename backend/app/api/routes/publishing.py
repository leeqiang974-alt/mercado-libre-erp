import asyncio
from datetime import UTC, datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models.publish_job import PublishJob, PublishJobStatus
from app.models.store import Store
from app.schemas.drafts import ProductDraftCreate
from app.schemas.publishing import (
    ListingChoice,
    PublishExecutionResult,
    PublishJobRead,
    PublishValidationResult,
)
from app.schemas.reviews import ReviewResponse
from app.services.draft_approvals import is_product_draft_approved
from app.services.draft_listing_configs import build_configured_draft
from app.services.integration_credentials import resolve_integration_credentials
from app.services.audit_events import create_audit_event
from app.services.meli.client import MercadoLibreClient
from app.services.meli.category_validation import validate_category_attributes
from app.services.meli.oauth import MercadoLibreOAuthClient
from app.services.meli.publisher import (
    SUPPORTED_LISTING_TYPE_IDS,
    execute_publish,
    validate_delivery_binding,
    validate_publish_request,
    validate_store_delivery,
)
from app.services.meli.shipping import find_non_full_shipping_selection
from app.services.meli.token_vault import resolve_fresh_store_access_token
from app.services.publish_jobs import (
    complete_publish_job,
    create_publish_job,
    list_publish_jobs,
    publish_blocking_errors,
    replay_publish_result,
    to_publish_job_read,
)
from app.services.reviews import get_publish_review

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
    errors = [*validation.errors, *store_errors]
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
    )


@router.get("/jobs", response_model=list[PublishJobRead])
def get_publish_jobs(db: Session = Depends(get_db)) -> list[PublishJobRead]:
    return list_publish_jobs(db)
