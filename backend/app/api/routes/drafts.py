from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.product_draft import ProductDraft
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
    limit: int = Query(default=60, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[ProductDraftRead]:
    # The listing rail only needs card metadata. Loading every description and
    # media array made #drafts unresponsive once the library grew large.
    drafts = list_product_drafts(db, limit=limit, compact=compact)
    jobs = db.query(PublishJob).order_by(PublishJob.id.desc()).all()
    latest: dict[int, PublishJob] = {}
    for job in jobs:
        latest.setdefault(job.product_draft_id, job)
    for draft in drafts:
        job = latest.get(draft.id)
        if job is None:
            continue
        draft.publication_status = job.status.value
        if job.status == PublishJobStatus.PUBLISHED:
            details = (job.response_summary_json or {}).get("response_details", {})
            rows = details.get("site_items", []) if isinstance(details, dict) else []
            draft.published_sites = [
                str(row.get("site_id")) for row in rows
                if isinstance(row, dict) and row.get("item_id") and row.get("site_id")
            ]
            if not draft.published_sites and job.meli_item_id:
                draft.published_sites = ["CBT"]
    return drafts


@router.get("/{product_draft_id}", response_model=ProductDraftRead)
def read_draft(
    product_draft_id: int,
    db: Session = Depends(get_db),
) -> ProductDraftRead:
    draft = db.get(ProductDraft, product_draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Product draft not found.")
    return to_draft_read(draft)


@router.delete("/{product_draft_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_draft(product_draft_id: int, db: Session = Depends(get_db)) -> Response:
    draft = db.get(ProductDraft, product_draft_id)
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
    draft = db.scalar(select(ProductDraft).where(ProductDraft.id == product_draft_id).with_for_update())
    if draft is None:
        raise HTTPException(status_code=404, detail="Product draft not found.")
    try:
        mirrored_urls = await mirror_images_to_oss(draft.image_urls_json or [], get_settings())
    except OssMirrorError as exc:
        raise HTTPException(status_code=422, detail=f"oss_image_mirror_failed: {exc}") from exc
    if mirrored_urls == (draft.image_urls_json or []):
        return to_draft_read(draft)
    previous_version = draft.content_version
    update_draft_content(
        db,
        product_draft_id,
        expected_content_version=previous_version,
        image_urls_json=mirrored_urls,
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
    draft, content, model = await generate_and_save_draft_content(
        db, get_settings(), product_draft_id, payload.category_id, set(payload.fields)
    )
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
