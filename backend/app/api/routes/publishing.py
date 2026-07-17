from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models.publish_job import PublishJobStatus
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
from app.services.audit_events import create_audit_event
from app.services.meli.client import MercadoLibreClient
from app.services.meli.category_validation import validate_category_attributes
from app.services.meli.oauth import MercadoLibreOAuthClient
from app.services.meli.publisher import (
    SUPPORTED_LISTING_TYPE_IDS,
    execute_publish,
    validate_publish_request,
    validate_store_site_match,
)
from app.services.meli.token_vault import resolve_fresh_store_access_token
from app.services.publish_jobs import (
    complete_publish_job,
    create_publish_job,
    get_publish_job_or_404,
    list_publish_jobs,
    replay_publish_result,
    to_publish_job_read,
)
from app.services.reviews import get_publish_review

router = APIRouter(prefix="/api/publishing", tags=["publishing"])
settings = get_settings()
SERVER_LISTING_TYPE_IDS = sorted(SUPPORTED_LISTING_TYPE_IDS)


def create_oauth_client() -> MercadoLibreOAuthClient:
    return MercadoLibreOAuthClient(
        client_id=settings.meli_client_id,
        client_secret=settings.meli_client_secret,
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
def publish_preview(payload: PublishPreviewRequest) -> PublishValidationResult:
    return validate_publish_request(
        draft=payload.draft,
        review=payload.review,
        listing_choice=payload.listing_choice,
        valid_listing_type_ids=SERVER_LISTING_TYPE_IDS,
        human_approved=payload.human_approved,
    )


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
    return _with_category_attribute_validation(db, draft, listing_choice, validation)


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
    site_errors = validate_store_site_match(store.site_id, listing_choice.site_id)
    validation_errors = [*validation.errors, *site_errors]
    validation_errors.extend(
        validate_category_attributes(
            db,
            draft.target_category_id,
            listing_choice.attributes,
            require_verified_metadata=settings.allow_live_publish,
        )
    )
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
    return to_publish_job_read(job)


@router.post("/jobs/{job_id}/retry", response_model=PublishExecutionResult)
async def retry_publish_job(job_id: int, db: Session = Depends(get_db)) -> PublishExecutionResult:
    job = get_publish_job_or_404(db, job_id)
    if job.status not in {PublishJobStatus.BLOCKED, PublishJobStatus.FAILED}:
        raise HTTPException(
            status_code=400,
            detail="Only blocked or failed publish jobs can be retried.",
        )

    draft, listing_choice = build_configured_draft(db, job.product_draft_id)
    review = get_publish_review(
        db,
        job.product_draft_id,
        (job.request_summary_json or {}).get("review_result_id"),
    )
    human_approved = is_product_draft_approved(db, job.product_draft_id)
    create_audit_event(
        db=db,
        actor_type="operator",
        actor_id="operator",
        action="publish.retry_requested",
        entity_type="publish_job",
        entity_id=str(job.id),
        before={
            "status": job.status.value if hasattr(job.status, "value") else str(job.status),
            "product_draft_id": job.product_draft_id,
            "store_id": job.store_id,
        },
        after={
            "retry_product_draft_id": job.product_draft_id,
            "retry_store_id": job.store_id,
            "listing_type_id": listing_choice.listing_type_id,
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
) -> PublishExecutionResult:
    store = db.get(Store, store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found.")
    validation = validate_publish_request(
        draft=draft,
        review=review,
        listing_choice=listing_choice,
        valid_listing_type_ids=valid_listing_type_ids,
        human_approved=human_approved,
    )
    validation_errors = [
        *validation.errors,
        *validate_store_site_match(store.site_id, listing_choice.site_id),
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
        job = create_publish_job(
            db=db,
            product_draft_id=product_draft_id,
            store_id=store_id,
            requested_by="operator",
            draft=draft,
            review=review,
            listing_choice=listing_choice,
            valid_listing_type_ids=valid_listing_type_ids,
        )
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
        oauth_client=create_oauth_client(),
    )
    if not access_token:
        job = create_publish_job(
            db=db,
            product_draft_id=product_draft_id,
            store_id=store_id,
            requested_by="operator",
            draft=draft,
            review=review,
            listing_choice=listing_choice,
            valid_listing_type_ids=valid_listing_type_ids,
        )
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
    job = create_publish_job(
        db=db,
        product_draft_id=product_draft_id,
        store_id=store_id,
        requested_by="operator",
        draft=draft,
        review=review,
        listing_choice=listing_choice,
        valid_listing_type_ids=valid_listing_type_ids,
    )
    if getattr(job, "_idempotent_replay", False):
        return replay_publish_result(job)
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
    errors = [
        *validation.errors,
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
            "human_approved": human_approved,
        },
        after={
            "status": result.status,
            "item_id": result.item_id,
            "permalink": result.permalink,
            "shipping_mode": result.shipping_mode,
            "errors": result.errors,
            "store_id": store_id,
        },
    )


@router.get("/jobs", response_model=list[PublishJobRead])
def get_publish_jobs(db: Session = Depends(get_db)) -> list[PublishJobRead]:
    return list_publish_jobs(db)
