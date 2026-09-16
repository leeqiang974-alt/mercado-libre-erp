from datetime import UTC, datetime
import asyncio

import httpx
from pydantic import BaseModel, Field
from urllib.parse import quote

from app.core.config import get_settings
from app.models.store import Store
from app.services.integration_credentials import resolve_integration_credentials
from app.services.meli.client import MercadoLibreClient
from app.services.meli.oauth import MercadoLibreOAuthClient
from app.services.meli.token_vault import resolve_fresh_store_access_token


from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import delete, select, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.product_draft import ProductDraft
from app.models.collection_job import CollectionJob, CollectionJobStatus
from app.models.cbt_listing_config import CbtListingConfig
from app.models.draft_listing_config import DraftListingConfig
from app.models.draft_pricing_config import DraftPricingConfig
from app.models.product_draft_approval import ProductDraftApproval
from app.models.review_job import ReviewJob
from app.models.review_result import ReviewResult
from app.models.publish_job import PublishJob, PublishJobStatus
from app.schemas.draft_approvals import DraftApprovalCreate, DraftApprovalRead
from app.schemas.draft_listing_config import DraftListingConfigRead, DraftListingConfigUpsert
from app.schemas.cbt_listing_config import CbtListingConfigRead, CbtListingConfigUpsert
from app.schemas.drafts import ProductDraftContentUpdate, ProductDraftRead
from app.schemas.draft_category import DraftCategoryRead, DraftCategoryUpdate
from app.schemas.content_generation import DraftContentGenerationRequest, DraftContentGenerationResponse
from app.schemas.attribute_mapping import AttributeSuggestionRead
from app.schemas.pricing import DraftPricingRead, DraftPricingUpsert
from app.services.draft_approvals import approve_product_draft, to_approval_read
from app.services.draft_listing_configs import (
    get_draft_listing_config,
    to_listing_config_read,
    upsert_draft_listing_config,
)
from app.services.cbt_listing_configs import (
    get_cbt_listing_config,
    to_cbt_listing_config_read,
    upsert_cbt_listing_config,
)
from app.services.drafts import (
    list_product_drafts,
    save_product_draft_content,
    to_draft_read,
    update_draft_content,
)
from app.services.audit_events import create_audit_event
from app.services.draft_publication_state import apply_draft_publication_state
from app.services.draft_pricing import (
    get_draft_pricing,
    require_current_draft_pricing,
    to_pricing_read,
    upsert_draft_pricing,
)
from app.services.meli.attribute_mapping import suggest_draft_category_attributes
from app.services.draft_categories import confirm_draft_category, to_category_read
from app.services.ai_content_generation import generate_and_save_draft_content
from app.core.config import get_settings
from app.services.storage.aliyun_oss import OssMirrorError, mirror_images_to_oss

router = APIRouter(prefix="/api/drafts", tags=["drafts"])


@router.get("", response_model=list[ProductDraftRead])
def list_drafts(
    compact: bool = Query(default=False),
    limit: int = Query(default=1000, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[ProductDraftRead]:
    # The listing rail only needs card metadata. Loading every description and
    # media array made #drafts unresponsive once the library grew large.
    drafts = list_product_drafts(db, limit=limit, compact=compact)
    return apply_draft_publication_state(db, drafts)


@router.get("/{product_draft_id}", response_model=ProductDraftRead)
def read_draft(
    product_draft_id: int,
    db: Session = Depends(get_db),
) -> ProductDraftRead:
    draft = db.get(ProductDraft, product_draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Product draft not found.")
    return apply_draft_publication_state(db, [to_draft_read(draft)])[0]


@router.delete("/{product_draft_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_draft(product_draft_id: int, db: Session = Depends(get_db)) -> Response:
    # Lock the draft before touching dependent rows. NOWAIT prevents timed-out
    # HTTP requests from continuing in a worker thread and forming a queue of
    # transactions behind a long AI/OSS operation on the same draft.
    try:
        draft = db.scalar(
            select(ProductDraft)
            .where(ProductDraft.id == product_draft_id)
            .with_for_update(nowait=True)
        )
    except OperationalError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="draft_busy_retry") from exc
    if draft is None:
        raise HTTPException(status_code=404, detail="Product draft not found.")
    active_publish = db.scalar(
        select(PublishJob).where(
            PublishJob.product_draft_id == product_draft_id,
            PublishJob.status.in_([
                PublishJobStatus.PENDING,
                PublishJobStatus.VALIDATING,
                PublishJobStatus.PUBLISHED,
            ]),
        ).limit(1)
    )
    if active_publish is not None:
        raise HTTPException(status_code=409, detail="published_or_active_draft_cannot_be_deleted")

    before = {
        "draft_id": draft.id,
        "source_product_id": draft.source_product_id,
        "target_site_id": draft.target_site_id,
        "title": draft.title,
        "status": draft.status.value if hasattr(draft.status, "value") else str(draft.status),
        "image_count": len(draft.image_urls_json or []),
        "video_count": len(draft.video_urls_json or []),
    }

    # A queued/running collection callback must not recreate a draft that the
    # operator intentionally removed. Keep the job as history, but close it as
    # skipped in the same transaction as the deletion.
    cancelled_collection_jobs: list[int] = []
    if draft.source_product_id is not None:
        try:
            active_collection_jobs = db.scalars(
                select(CollectionJob)
                .where(
                    CollectionJob.source_product_id == draft.source_product_id,
                    CollectionJob.status.in_([
                        CollectionJobStatus.PENDING,
                        CollectionJobStatus.RUNNING,
                    ]),
                )
                .with_for_update(nowait=True)
            ).all()
        except OperationalError as exc:
            db.rollback()
            raise HTTPException(status_code=409, detail="draft_busy_retry") from exc
        for job in active_collection_jobs:
            previous_status = job.status.value
            job.status = CollectionJobStatus.SKIPPED
            job.message = "草稿已由操作员删除；采集任务已终止，禁止自动重建。"
            job.completed_at = datetime.now(UTC)
            job.claimed_by = None
            job.claimed_at = None
            cancelled_collection_jobs.append(job.id)
            create_audit_event(
                db=db,
                actor_type="human",
                actor_id="operator",
                action="collection_job.skipped_after_draft_delete",
                entity_type="collection_job",
                entity_id=str(job.id),
                before={"status": previous_status},
                after={
                    "status": CollectionJobStatus.SKIPPED.value,
                    "source_product_id": draft.source_product_id,
                    "deleted_draft_id": product_draft_id,
                },
                commit=False,
            )

    # Collection jobs are source-history records.  Keep the history but detach
    # the optional draft reference so deleting an unpublished draft cannot
    # crash with a database foreign-key violation.
    db.execute(
        update(CollectionJob)
        .where(CollectionJob.draft_id == product_draft_id)
        .values(draft_id=None)
    )
    # These records are draft-owned working configuration/review state.  A
    # draft that has not been published may remove them together with itself.
    for model in (
        ProductDraftApproval,
        CbtListingConfig,
        DraftListingConfig,
        DraftPricingConfig,
        ReviewJob,
        ReviewResult,
        PublishJob,
    ):
        db.execute(delete(model).where(model.product_draft_id == product_draft_id))
    create_audit_event(
        db=db,
        actor_type="human",
        actor_id="operator",
        action="draft.deleted",
        entity_type="product_draft",
        entity_id=str(product_draft_id),
        before=before,
        after={"deleted": True, "cancelled_collection_job_ids": cancelled_collection_jobs},
        commit=False,
    )
    db.delete(draft)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/{product_draft_id}/content", response_model=ProductDraftRead)
def save_draft_content(
    product_draft_id: int,
    payload: ProductDraftContentUpdate,
    db: Session = Depends(get_db),
) -> ProductDraftRead:
    return to_draft_read(save_product_draft_content(db, product_draft_id, payload))


@router.post("/{product_draft_id}/mirror-images-to-oss", response_model=ProductDraftRead)
async def mirror_draft_images_to_oss(
    product_draft_id: int,
    db: Session = Depends(get_db),
) -> ProductDraftRead:
    """Persist stable, verified OSS image URLs before Global Selling publishing."""
    # Never hold a draft row lock while downloading/uploading remote images.
    # AI/manual saves and publish preflight must remain responsive while OSS is
    # slow. Re-lock only for the final compare-and-write below.
    draft = db.get(ProductDraft, product_draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Product draft not found.")
    original_urls = list(draft.image_urls_json or [])
    try:
        mirrored_urls = await mirror_images_to_oss(original_urls, get_settings())
    except OssMirrorError as exc:
        raise HTTPException(status_code=422, detail=f"oss_image_mirror_failed: {exc}") from exc
    draft = db.scalar(
        select(ProductDraft)
        .where(ProductDraft.id == product_draft_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if draft is None:
        raise HTTPException(status_code=404, detail="Product draft not found.")
    if list(draft.image_urls_json or []) != original_urls:
        raise HTTPException(status_code=409, detail="draft_images_changed_during_mirror")
    if mirrored_urls == original_urls:
        return to_draft_read(draft)
    previous_version = draft.content_version
    update_draft_content(
        db,
        product_draft_id,
        expected_content_version=previous_version,
        image_urls_json=mirrored_urls,
    )
    create_audit_event(
        db=db,
        actor_type="system",
        actor_id="oss_image_normalizer",
        action="draft.images_normalized",
        entity_type="product_draft",
        entity_id=str(product_draft_id),
        before={"content_version": previous_version, "image_count": len(original_urls)},
        after={
            "content_version": previous_version + 1,
            "image_count": len(mirrored_urls),
            "discarded_count": max(0, len(original_urls) - len(mirrored_urls)),
            "oss_mirrored": True,
        },
        commit=False,
    )
    db.commit()
    db.refresh(draft)
    return to_draft_read(draft)


@router.put("/{product_draft_id}/category", response_model=DraftCategoryRead)
def confirm_category(
    product_draft_id: int,
    payload: DraftCategoryUpdate,
    db: Session = Depends(get_db),
) -> DraftCategoryRead:
    draft, attributes, verified = confirm_draft_category(db, product_draft_id, payload)
    return to_category_read(draft, attributes, verified)


@router.post("/{product_draft_id}/generate-content", response_model=DraftContentGenerationResponse)
async def generate_content(
    product_draft_id: int,
    payload: DraftContentGenerationRequest,
    db: Session = Depends(get_db),
) -> DraftContentGenerationResponse:
    runtime_settings = get_settings()
    try:
        draft, content, model, generation_meta = await generate_and_save_draft_content(
            db,
            runtime_settings,
            product_draft_id,
            payload.category_id,
            set(payload.fields),
            set(payload.regenerate_fields),
            timeout_seconds=runtime_settings.ai_content_generation_timeout_seconds,
            require_verified_category=False,
        )
    except HTTPException as exc:
        # Every attempted paid/manual generation needs an operator-visible
        # trace, including rejections before a provider request is sent.  Keep
        # only a normalized code; credentials and provider responses never go
        # into the audit table.
        detail = exc.detail
        if isinstance(detail, dict):
            code = str(detail.get("code") or "request_rejected")[:120]
            failed_field = str(detail.get("field") or "")[:20] or None
            attempts = detail.get("attempts")
            retryable = bool(detail.get("retryable"))
            attempt_counts = detail.get("attempt_counts")
            field_outcomes = detail.get("field_outcomes")
        elif isinstance(detail, str):
            code = detail[:120]
            failed_field = None
            attempts = None
            retryable = False
            attempt_counts = None
            field_outcomes = None
        else:
            code = "request_rejected"
            failed_field = None
            attempts = None
            retryable = False
            attempt_counts = None
            field_outcomes = None
        failure_after = {
            "status_code": exc.status_code,
            "code": code,
            "requested_fields": sorted(set(payload.fields)),
            "regenerate_fields": sorted(set(payload.regenerate_fields)),
        }
        if failed_field:
            failure_after["failed_field"] = failed_field
        if isinstance(attempts, int):
            failure_after["attempts"] = attempts
        if retryable:
            failure_after["retryable"] = True
        if isinstance(attempt_counts, dict):
            failure_after["attempt_counts"] = attempt_counts
        if isinstance(field_outcomes, dict):
            failure_after["field_outcomes"] = field_outcomes
        create_audit_event(
            db=db,
            actor_type="system",
            actor_id=runtime_settings.content_generation_provider,
            action="draft.ai_content_failed",
            entity_type="product_draft",
            entity_id=str(product_draft_id),
            after=failure_after,
        )
        raise
    except Exception:
        create_audit_event(
            db=db,
            actor_type="system",
            actor_id=runtime_settings.content_generation_provider,
            action="draft.ai_content_failed",
            entity_type="product_draft",
            entity_id=str(product_draft_id),
            after={
                "status_code": 500,
                "code": "internal_error",
                "requested_fields": sorted(set(payload.fields)),
                "regenerate_fields": sorted(set(payload.regenerate_fields)),
            },
        )
        raise
    return DraftContentGenerationResponse(
        draft=to_draft_read(draft),
        title=content.title,
        description=content.description,
        brand=content.brand,
        validation={
            "title_length": len(content.title),
            "title_valid": True,
            "description_valid": True,
            "warranty_included": True,
            **generation_meta,
        },
        model=model,
    )


@router.put("/{product_draft_id}/pricing", response_model=DraftPricingRead)
def save_pricing(
    product_draft_id: int,
    payload: DraftPricingUpsert,
    db: Session = Depends(get_db),
) -> DraftPricingRead:
    pricing, draft = upsert_draft_pricing(db, product_draft_id, payload)
    return to_pricing_read(pricing, draft)


@router.get("/{product_draft_id}/pricing", response_model=DraftPricingRead | None)
def read_pricing(
    product_draft_id: int,
    optional: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> DraftPricingRead | None:
    try:
        pricing = get_draft_pricing(db, product_draft_id)
    except HTTPException as exc:
        if optional and exc.status_code == 404:
            return None
        raise
    draft = db.get(ProductDraft, product_draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Product draft not found.")
    require_current_draft_pricing(db, draft)
    return to_pricing_read(pricing, to_draft_read(draft))


@router.put("/{product_draft_id}/listing-config", response_model=DraftListingConfigRead)
def save_listing_config(
    product_draft_id: int,
    payload: DraftListingConfigUpsert,
    db: Session = Depends(get_db),
) -> DraftListingConfigRead:
    config, draft = upsert_draft_listing_config(db, product_draft_id, payload)
    return to_listing_config_read(config, draft)


@router.get("/{product_draft_id}/listing-config", response_model=DraftListingConfigRead | None)
def read_listing_config(
    product_draft_id: int,
    optional: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> DraftListingConfigRead | None:
    try:
        config = get_draft_listing_config(db, product_draft_id)
        draft = db.get(ProductDraft, product_draft_id)
        if draft is None:
            raise HTTPException(status_code=404, detail="Product draft not found.")
        return to_listing_config_read(config, to_draft_read(draft))
    except HTTPException as exc:
        if optional and exc.status_code == 404:
            return None
        raise


@router.put("/{product_draft_id}/cbt-listing-config", response_model=CbtListingConfigRead)
def save_cbt_listing_config(
    product_draft_id: int,
    payload: CbtListingConfigUpsert,
    db: Session = Depends(get_db),
) -> CbtListingConfigRead:
    config, draft = upsert_cbt_listing_config(db, product_draft_id, payload)
    return to_cbt_listing_config_read(config, draft)


@router.get("/{product_draft_id}/cbt-listing-config", response_model=CbtListingConfigRead | None)
def read_cbt_listing_config(
    product_draft_id: int,
    optional: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> CbtListingConfigRead | None:
    try:
        config = get_cbt_listing_config(db, product_draft_id)
        draft = db.get(ProductDraft, product_draft_id)
        if draft is None:
            raise HTTPException(status_code=404, detail="Product draft not found.")
        return to_cbt_listing_config_read(config, draft)
    except HTTPException as exc:
        if optional and exc.status_code == 404:
            return None
        raise


@router.get(
    "/{product_draft_id}/attribute-suggestions",
    response_model=AttributeSuggestionRead,
)
def read_attribute_suggestions(
    product_draft_id: int,
    category_id: str = Query(..., min_length=1, max_length=40),
    db: Session = Depends(get_db),
) -> AttributeSuggestionRead:
    return suggest_draft_category_attributes(db, product_draft_id, category_id)


@router.post("/{product_draft_id}/approval", response_model=DraftApprovalRead)
def approve_draft(
    product_draft_id: int,
    payload: DraftApprovalCreate,
    db: Session = Depends(get_db),
) -> DraftApprovalRead:
    return to_approval_read(approve_product_draft(db, product_draft_id, payload))



def _draft_create_meli_client(access_token: str, timeout: float = 15) -> MercadoLibreClient:
    return MercadoLibreClient(access_token=access_token, timeout=timeout)


def _draft_create_oauth_client(db: Session) -> MercadoLibreOAuthClient:
    settings = get_settings()
    credentials = resolve_integration_credentials(db, settings)
    return MercadoLibreOAuthClient(
        client_id=credentials.meli_client_id,
        client_secret=credentials.meli_client_secret,
        redirect_uri=settings.meli_redirect_uri,
    )


class DraftAutoFixCategoryRequest(BaseModel):
    store_id: int
    candidate_category_id: str = ""


@router.post("/{draft_id}/auto-fix-category")
async def auto_fix_draft_category(
    draft_id: int,
    payload: DraftAutoFixCategoryRequest,
    db: Session = Depends(get_db),
) -> dict:
    """【2026-09-16 迭代】发布失败分类自动校正。

    按草稿标题调美客多 CBT 分类预测（/marketplace/domain_discovery/search），
    自动更新草稿 target_category_id；同步清空 listing config 的分类与属性
    （分类变更后属性必须重选，避免用旧分类属性发布报错）。不自动重发，
    由前端展示新分类与候选后用户确认再发布。
    """
    settings = get_settings()
    draft = db.get(ProductDraft, draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Product draft not found.")
    store = db.get(Store, payload.store_id)
    if store is None or store.site_id.strip().upper() != "CBT":
        raise HTTPException(
            status_code=422, detail="A connected CBT Global Selling store is required."
        )
    if store.oauth_status != "connected":
        raise HTTPException(status_code=409, detail="Store is not connected.")
    query = " ".join((draft.title or "").split())
    if not query:
        raise HTTPException(
            status_code=409, detail="Draft title is empty; cannot predict a category."
        )
    access_token = await resolve_fresh_store_access_token(
        db=db,
        store=store,
        encryption_key=settings.token_encryption_key,
        oauth_client=_draft_create_oauth_client(db),
    )
    if not access_token:
        raise HTTPException(status_code=409, detail="Store access token is unavailable.")
    try:
        data = await _draft_create_meli_client(access_token, timeout=15).get(
            f"/marketplace/domain_discovery/search?q={quote(query, safe='')}"
        )
    except (httpx.HTTPError, asyncio.TimeoutError) as exc:
        raise HTTPException(
            status_code=502, detail="CBT category prediction is unavailable."
        ) from exc
    predictions: list[dict] = []
    for item in data if isinstance(data, list) else []:
        if not isinstance(item, dict):
            continue
        category_id = str(item.get("category_id") or "").strip().upper()
        if not category_id.startswith("CBT"):
            continue
        predictions.append(
            {
                "category_id": category_id,
                "category_name": str(
                    item.get("category_name") or item.get("domain_name") or ""
                ).strip(),
                "domain_name": str(item.get("domain_name") or "").strip(),
                "parent_path": str(item.get("parent_path") or "").strip(),
            }
        )
    if not predictions:
        raise HTTPException(
            status_code=409, detail="No CBT category suggested by title."
        )
    candidate = payload.candidate_category_id.strip().upper()
    if candidate:
        if candidate not in [p["category_id"] for p in predictions]:
            raise HTTPException(
                status_code=422, detail="Candidate category is not in suggestions."
            )
        selected = candidate
    else:
        current = (draft.target_category_id or "").strip().upper()
        chosen = next(
            (p for p in predictions if p["category_id"] != current),
            predictions[0],
        )
        selected = chosen["category_id"]
    changed = selected != (draft.target_category_id or "").strip().upper()
    draft.target_category_id = selected
    config = db.execute(
        select(CbtListingConfig).where(
            CbtListingConfig.product_draft_id == draft_id
        )
    ).scalar_one_or_none()
    if config is not None:
        config.category_id = selected
        config.attributes_json = []
    db.commit()
    return {
        "draft_id": draft_id,
        "category_id": selected,
        "changed": changed,
        "predictions": predictions[:6],
        "auto_applied": True,
        "note": "分类已按标题建议校正；属性已清空，需重新加载属性后再发布。",
    }
