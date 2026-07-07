from collections.abc import Awaitable, Callable

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
from app.services.meli.client import MercadoLibreClient
from app.services.meli.oauth import MercadoLibreOAuthClient
from app.services.meli.publisher import execute_publish
from app.services.meli.token_vault import resolve_fresh_store_access_token
from app.services.publish_jobs import complete_publish_job, review_from_job_summary

Publisher = Callable[..., Awaitable[PublishExecutionResult]]
WorkerSummary = dict[str, int]


async def run_pending_publish_jobs(
    db: Session,
    limit: int = 10,
    publisher: Publisher | None = None,
    allow_live_publish: bool | None = None,
    token_encryption_key: str | None = None,
) -> WorkerSummary:
    jobs = db.scalars(
        select(PublishJob)
        .where(PublishJob.status == PublishJobStatus.PENDING)
        .order_by(PublishJob.id)
        .limit(limit)
    ).all()
    summary = {"processed": 0, "published": 0, "blocked": 0, "failed": 0}
    for job in jobs:
        result = await run_pending_publish_job(
            db=db,
            job_id=job.id,
            publisher=publisher,
            allow_live_publish=allow_live_publish,
            token_encryption_key=token_encryption_key,
        )
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
    job = db.get(PublishJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Publish job not found.")
    if job.status != PublishJobStatus.PENDING:
        raise HTTPException(status_code=400, detail="Publish job is not pending.")

    job.status = PublishJobStatus.VALIDATING
    db.commit()
    db.refresh(job)

    try:
        draft, listing_choice = build_configured_draft(db, job.product_draft_id)
        review = review_from_job_summary(job)
        human_approved = is_product_draft_approved(db, job.product_draft_id)
        store = db.get(Store, job.store_id)
        if store is None:
            result = PublishExecutionResult(status="failed", errors=["store_not_found"])
        else:
            settings = get_settings()
            access_token = await resolve_fresh_store_access_token(
                db=db,
                store=store,
                encryption_key=token_encryption_key or settings.token_encryption_key,
                oauth_client=_create_oauth_client(),
            )
            if not access_token:
                result = PublishExecutionResult(status="blocked", errors=["store_access_token_required"])
            else:
                publish = publisher or execute_publish
                result = await publish(
                    client=MercadoLibreClient(access_token=access_token),
                    draft=draft,
                    review=review,
                    listing_choice=listing_choice,
                    valid_listing_type_ids=[listing_choice.listing_type_id],
                    human_approved=human_approved,
                    allow_live_publish=(
                        settings.allow_live_publish
                        if allow_live_publish is None
                        else allow_live_publish
                    ),
                )
    except HTTPException as exc:
        result = PublishExecutionResult(status="failed", errors=[str(exc.detail)])

    complete_publish_job(db, job, result)
    _audit_publish_job(db=db, job=job, result=result)
    return result.model_copy(update={"job_id": job.id})


def _create_oauth_client() -> MercadoLibreOAuthClient:
    settings = get_settings()
    return MercadoLibreOAuthClient(
        client_id=settings.meli_client_id,
        client_secret=settings.meli_client_secret,
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
        },
        after={
            "status": result.status,
            "item_id": result.item_id,
            "permalink": result.permalink,
            "errors": result.errors,
            "store_id": job.store_id,
        },
    )
