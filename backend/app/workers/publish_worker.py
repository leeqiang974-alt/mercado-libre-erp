from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.publish_job import PublishJob, PublishJobStatus
from app.models.store import Store
from app.schemas.publishing import PublishExecutionResult
from app.services.audit_events import create_audit_event
from app.services.draft_approvals import is_product_draft_approved
from app.services.draft_listing_configs import build_configured_draft
from app.services.integration_credentials import resolve_integration_credentials
from app.services.meli.client import MercadoLibreClient
from app.services.meli.category_validation import validate_category_attributes
from app.services.meli.oauth import MercadoLibreOAuthClient
from app.services.meli.listing_type_validation import validate_store_category_listing_type
from app.services.meli.publisher import (
    SUPPORTED_LISTING_TYPE_IDS,
    execute_publish,
    validate_publish_request,
    validate_store_delivery,
)
from app.services.meli.token_vault import resolve_fresh_store_access_token
from app.services.publish_jobs import (
    complete_publish_job,
    publish_blocking_errors,
    recover_stale_publish_jobs,
)
from app.services.reviews import get_publish_review
from app.api.routes.publishing import execute_cbt_global_publish_job

Publisher = Callable[..., Awaitable[PublishExecutionResult]]
WorkerSummary = dict[str, int]


async def run_pending_publish_jobs(
    db: Session,
    limit: int = 10,
    publisher: Publisher | None = None,
    allow_live_publish: bool | None = None,
    token_encryption_key: str | None = None,
) -> WorkerSummary:
    recovered = recover_stale_publish_jobs(db, get_settings().job_stale_after_seconds)
    jobs = db.scalars(
        select(PublishJob)
        .where(PublishJob.status == PublishJobStatus.PENDING)
        .order_by(PublishJob.id)
        .limit(limit)
    ).all()
    summary = {
        "processed": 0,
        "published": 0,
        "blocked": 0,
        "failed": 0,
        "recovered": recovered,
    }
    for job in jobs:
        try:
            result = await run_pending_publish_job(
                db=db,
                job_id=job.id,
                publisher=publisher,
                allow_live_publish=allow_live_publish,
                token_encryption_key=token_encryption_key,
            )
        except HTTPException as exc:
            if exc.status_code != 409:
                raise
            db.rollback()
            continue
        summary["processed"] += 1
        if result.status == "published":
            summary["published"] += 1
        elif result.status == "blocked":
            summary["blocked"] += 1
        else:
            summary["failed"] += 1
    return summary


async def run_pending_publish_job(
    db: Session,
    job_id: int,
    publisher: Publisher | None = None,
    allow_live_publish: bool | None = None,
    token_encryption_key: str | None = None,
) -> PublishExecutionResult:
    job = db.scalar(
        select(PublishJob)
        .where(
            PublishJob.id == job_id,
            PublishJob.status == PublishJobStatus.PENDING,
        )
        .with_for_update(skip_locked=True)
    )
    if job is None:
        existing = db.get(PublishJob, job_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="Publish job not found.")
        raise HTTPException(status_code=409, detail="Publish job was claimed by another worker.")

    job.status = PublishJobStatus.VALIDATING
    job.started_at = datetime.now(UTC)
    db.commit()
    db.refresh(job)

    try:
        if (job.request_summary_json or {}).get("publication_model") == "traditional_global":
            result = await execute_cbt_global_publish_job(
                db=db,
                job=job,
                token_encryption_key=(
                    get_settings().token_encryption_key
                    if token_encryption_key is None
                    else token_encryption_key
                ),
            )
        else:
            draft, listing_choice = build_configured_draft(db, job.product_draft_id)
            review = get_publish_review(
                db,
                job.product_draft_id,
                (job.request_summary_json or {}).get("review_result_id"),
            )
            human_approved = is_product_draft_approved(db, job.product_draft_id)
            valid_listing_type_ids = sorted(SUPPORTED_LISTING_TYPE_IDS)
            store = db.get(Store, job.store_id)
            if store is None:
                result = PublishExecutionResult(status="failed", errors=["store_not_found"])
            elif (
                delivery_errors := validate_store_delivery(
                    store.id, store.site_id, store.oauth_status, listing_choice
                )
            ):
                result = PublishExecutionResult(status="blocked", errors=delivery_errors)
            else:
                validation = validate_publish_request(
                    draft=draft,
                    review=review,
                    listing_choice=listing_choice,
                    valid_listing_type_ids=valid_listing_type_ids,
                    human_approved=human_approved,
                )
                category_errors = validate_category_attributes(
                    db,
                    draft.target_category_id,
                    listing_choice.attributes,
                    require_verified_metadata=(
                        get_settings().allow_live_publish
                        if allow_live_publish is None
                        else allow_live_publish
                    ),
                )
                listing_type_errors = validate_store_category_listing_type(
                    db,
                    store.id,
                    draft.target_category_id,
                    listing_choice.listing_type_id,
                    require_verified_metadata=(
                        get_settings().allow_live_publish
                        if allow_live_publish is None
                        else allow_live_publish
                    ),
                    max_age_seconds=get_settings().listing_type_cache_ttl_seconds,
                )
                if category_errors or listing_type_errors:
                    validation = validation.model_copy(
                        update={
                            "allowed": False,
                            "errors": [
                                *validation.errors,
                                *listing_type_errors,
                                *category_errors,
                            ],
                        }
                    )
                if not validation.allowed:
                    result = PublishExecutionResult(status="blocked", errors=validation.errors)
                else:
                    result = await _publish_job(
                        db=db,
                        product_draft_id=job.product_draft_id,
                        store=store,
                        draft=draft,
                        review=review,
                        listing_choice=listing_choice,
                        human_approved=human_approved,
                        valid_listing_type_ids=valid_listing_type_ids,
                        publisher=publisher,
                        allow_live_publish=allow_live_publish,
                        token_encryption_key=token_encryption_key,
                        publish_reference=(job.request_summary_json or {}).get(
                            "publish_reference", ""
                        ),
                    )
    except HTTPException as exc:
        result = PublishExecutionResult(
            status="blocked" if 400 <= exc.status_code < 500 else "failed",
            errors=publish_blocking_errors(exc.detail),
        )
    except Exception as exc:
        result = PublishExecutionResult(
            status="failed", errors=[f"worker_error:{type(exc).__name__}"]
        )

    complete_publish_job(db, job, result)
    _audit_publish_job(db=db, job=job, result=result)
    return result.model_copy(update={"job_id": job.id})


async def _publish_job(
    db: Session,
    product_draft_id: int,
    store: Store,
    draft,
    review,
    listing_choice,
    human_approved: bool,
    valid_listing_type_ids: list[str],
    publisher: Publisher | None,
    allow_live_publish: bool | None,
    token_encryption_key: str | None,
    publish_reference: str,
) -> PublishExecutionResult:
    settings = get_settings()
    if not publish_reference:
        return PublishExecutionResult(
            status="blocked", errors=["publish_reference_required"]
        )
    access_token = await resolve_fresh_store_access_token(
        db=db,
        store=store,
        encryption_key=token_encryption_key or settings.token_encryption_key,
        oauth_client=_create_oauth_client(db),
    )
    if not access_token:
        return PublishExecutionResult(status="blocked", errors=["store_access_token_required"])
    draft, listing_choice = build_configured_draft(
        db, product_draft_id, lock_draft=True
    )
    review = get_publish_review(db, product_draft_id, review.review_result_id)
    human_approved = is_product_draft_approved(db, product_draft_id)
    store = db.scalar(
        select(Store)
        .where(Store.id == store.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if store is None:
        return PublishExecutionResult(status="failed", errors=["store_not_found"])
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
            require_verified_metadata=(
                settings.allow_live_publish
                if allow_live_publish is None
                else allow_live_publish
            ),
            max_age_seconds=settings.listing_type_cache_ttl_seconds,
        ),
        *validate_store_delivery(
            store.id, store.site_id, store.oauth_status, listing_choice
        ),
        *validate_category_attributes(
            db,
            draft.target_category_id,
            listing_choice.attributes,
            require_verified_metadata=(
                settings.allow_live_publish
                if allow_live_publish is None
                else allow_live_publish
            ),
        ),
    ]
    if final_errors:
        return PublishExecutionResult(status="blocked", errors=final_errors)
    publish = publisher or execute_publish
    try:
        return await publish(
            client=MercadoLibreClient(access_token=access_token),
            seller_id=store.seller_id,
            draft=draft,
            review=review,
            listing_choice=listing_choice,
            valid_listing_type_ids=valid_listing_type_ids,
            human_approved=human_approved,
            allow_live_publish=(
                settings.allow_live_publish if allow_live_publish is None else allow_live_publish
            ),
            publish_reference=publish_reference,
        )
    except Exception:
        return PublishExecutionResult(
            status="blocked",
            errors=["publish_outcome_unknown_manual_reconciliation_required"],
        )


def _create_oauth_client(db: Session) -> MercadoLibreOAuthClient:
    settings = get_settings()
    credentials = resolve_integration_credentials(db, settings)
    return MercadoLibreOAuthClient(
        client_id=credentials.meli_client_id,
        client_secret=credentials.meli_client_secret,
        redirect_uri=settings.meli_redirect_uri,
    )


def _audit_publish_job(db: Session, job: PublishJob, result: PublishExecutionResult) -> None:
    summary = job.request_summary_json or {}
    create_audit_event(
        db=db,
        actor_type="worker",
        actor_id="publish_worker",
        action="publish.executed",
        entity_type="publish_job",
        entity_id=str(job.id),
        before={
            "product_draft_id": job.product_draft_id,
            "store_id": job.store_id,
            "listing_type_id": summary.get("listing_type_id", ""),
            "shipping_mode": summary.get("shipping_mode", ""),
            "shipping_logistic_type": summary.get("shipping_logistic_type", ""),
        },
        after={
            "status": result.status,
            "item_id": result.item_id,
            "permalink": result.permalink,
            "shipping_mode": result.shipping_mode,
            "shipping_logistic_type": result.shipping_logistic_type,
            "errors": result.errors,
            "store_id": job.store_id,
        },
    )
