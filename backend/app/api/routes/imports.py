from typing import Annotated
from datetime import UTC, datetime
import re
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, text
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.db.session import get_db
from app.core.config import get_settings
from app.schemas.drafts import PersistedDraftResponse, ProductDraftCreate, ProductDraftRead
from app.services.amazon.collector import (
    CollectionResult,
    collect_amazon_page,
    normalize_amazon_product_url,
    validate_amazon_snapshot,
)
from app.services.amazon.normalizer import normalize_amazon_product
from app.services.amazon.import_file import MAX_IMPORT_FILE_BYTES, parse_amazon_url_file
from app.services.amazon.discovery import discover_amazon_products
from app.services.amazon.throttle import record_domain_outcome, reserve_domain_request
from app.services.drafts import create_product_draft, to_draft_read, update_draft_content
from app.services.amazon.media import select_listing_images
from app.services.audit_events import create_audit_event
from app.services.source_products import (
    EXACT_PAGE_EVIDENCE_STATUSES,
    create_or_get_source_variant_draft,
    create_source_product,
    selected_source_variant,
    to_source_product_read,
)
from app.models.source_product import SourceProduct, SourceProductStatus
from app.models.product_draft import ProductDraft
from app.services.collection_jobs import (
    create_collection_job,
    create_collection_jobs,
    list_collection_jobs,
    list_collection_jobs_by_ids,
    run_collection_job,
    to_collection_job_read,
)
from app.schemas.collection_jobs import (
    CollectionBatchItemRead,
    CollectionBatchRead,
    CollectionJobRead,
    SourceVariantCollectionBatchRead,
)
from app.models.collection_job import CollectionJob, CollectionJobStatus
from app.models.keyword_collection_campaign import KeywordCampaignStatus, KeywordCollectionCampaign
from app.services.amazon.keyword_campaigns import normalize_keywords
from app.services.meli.sites import SITE_CURRENCIES
from app.schemas.source_products import (
    AmazonSourceSnapshot,
    SourceProductRead,
    SourceVariantCollectionCreate,
    SourceVariantDraftCreate,
)

router = APIRouter(prefix="/api/imports", tags=["imports"])
settings = get_settings()
AmazonProductUrl = Annotated[str, Field(max_length=2048)]


class AmazonHtmlImport(BaseModel):
    source_url: AmazonProductUrl
    html: str
    target_site_id: str = "MLM"
    persist: bool = False
    collection_job_id: int | None = Field(default=None, ge=1)


class AmazonUrlImport(BaseModel):
    source_url: AmazonProductUrl
    target_site_id: str = "MLM"
    persist: bool = False


class AmazonUrlBatchImport(BaseModel):
    source_urls: list[AmazonProductUrl] = Field(min_length=1, max_length=100)
    target_site_id: str = "MLM"
    allow_existing: bool = False


class AmazonExtensionCapture(BaseModel):
    source_url: AmazonProductUrl
    target_site_id: str = "CBT"
    snapshot: dict = Field(default_factory=dict)


def _extension_capture_quality(
    snapshot: AmazonSourceSnapshot,
    *,
    image_count: int,
    video_count: int,
) -> dict[str, object]:
    """Return an honest capture summary without treating optional media as an error."""
    issues: list[str] = []
    if not snapshot.title.strip():
        issues.append("标题未读取到")
    if image_count == 0:
        issues.append("未读取到可用主图")
    if not snapshot.description.strip() and not snapshot.bullets:
        issues.append("描述和五点卖点均未读取到")
    return {
        "complete": not issues,
        "issues": issues,
        "image_count": image_count,
        "video_count": video_count,
        "variant_count": len(snapshot.variants),
        "technical_detail_count": len(snapshot.technical_details),
    }


class AmazonDiscoveryImport(BaseModel):
    keyword: str = Field(min_length=2, max_length=160)
    domain: str = Field(default="amazon.com")
    target_site_id: str = "CBT"
    limit: int = Field(default=20, ge=1, le=50)


class KeywordCampaignCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    keywords: list[str] = Field(min_length=1, max_length=100)
    domain: str = Field(default="amazon.com", max_length=120)
    target_site_id: str = "CBT"
    pages_per_keyword: int = Field(default=2, ge=1, le=10)


class KeywordCampaignRead(BaseModel):
    id: int
    name: str
    domain: str
    target_site_id: str
    keyword_count: int
    pages_per_keyword: int
    status: str
    current_keyword: str | None
    current_page: int
    discovered_count: int
    queued_count: int
    duplicate_count: int
    message: str
    keywords: list[dict[str, int | str]] = []


def _campaign_read(row: KeywordCollectionCampaign, db: Session) -> KeywordCampaignRead:
    keywords = row.keywords_json or []
    current = keywords[row.current_keyword_index] if row.current_keyword_index < len(keywords) else None
    progress_rows = (
        db.query(CollectionJob.campaign_keyword, CollectionJob.status, func.count(CollectionJob.id))
        .filter(CollectionJob.campaign_id == row.id)
        .group_by(CollectionJob.campaign_keyword, CollectionJob.status)
        .all()
    )
    progress: dict[str, dict[str, int | str]] = {
        keyword: {
            "keyword": keyword,
            "discovered": 0,
            "completed": 0,
            "running": 0,
            "pending": 0,
            "failed": 0,
            "needs_manual_action": 0,
        }
        for keyword in keywords
    }
    for keyword, status, count in progress_rows:
        if not keyword:
            continue
        item = progress.setdefault(keyword, {"keyword": keyword, "discovered": 0, "completed": 0, "running": 0, "pending": 0, "failed": 0, "needs_manual_action": 0})
        item["discovered"] = int(item["discovered"]) + int(count)
        if status in item:
            item[status] = int(item[status]) + int(count)
    for item in progress.values():
        item["processed"] = int(item["completed"]) + int(item["failed"]) + int(item["needs_manual_action"])
        item["status"] = "处理中" if int(item["running"]) else ("待处理" if int(item["pending"]) else ("已完成" if int(item["processed"]) else "未发现结果"))
    return KeywordCampaignRead(id=row.id, name=row.name, domain=row.domain, target_site_id=row.target_site_id,
        keyword_count=len(keywords), pages_per_keyword=row.pages_per_keyword, status=row.status,
        current_keyword=current, current_page=row.current_page, discovered_count=row.discovered_count,
        queued_count=row.queued_count, duplicate_count=row.duplicate_count, message=row.message,
        keywords=list(progress.values()))


@router.post("/amazon-html")
def import_amazon_html(
    payload: AmazonHtmlImport, db: Session = Depends(get_db)
) -> ProductDraftCreate | PersistedDraftResponse:
    source_url = _normalized_amazon_url_or_422(payload.source_url)
    target_site_id = _target_site_or_422(payload.target_site_id)
    try:
        parsed = validate_amazon_snapshot(source_url, payload.html)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    draft = normalize_amazon_product(parsed, target_site_id)
    if payload.collection_job_id is not None and not payload.persist:
        raise HTTPException(status_code=422, detail="snapshot_job_resolution_requires_persist")
    if not payload.persist:
        return draft
    job = None
    if payload.collection_job_id is not None:
        job = (
            db.query(CollectionJob)
            .filter(CollectionJob.id == payload.collection_job_id)
            .with_for_update()
            .populate_existing()
            .one_or_none()
        )
        if job is None:
            raise HTTPException(status_code=404, detail="collection_job_not_found")
        if job.status != CollectionJobStatus.NEEDS_MANUAL_ACTION:
            raise HTTPException(
                status_code=409,
                detail="collection_job_not_waiting_for_snapshot",
            )
        try:
            job_source_url = normalize_amazon_product_url(job.source_url)
        except ValueError as exc:
            raise HTTPException(
                status_code=409,
                detail="collection_job_source_invalid",
            ) from exc
        if job_source_url != source_url:
            raise HTTPException(status_code=409, detail="collection_job_source_mismatch")
        if job.target_site_id != target_site_id:
            raise HTTPException(status_code=409, detail="collection_job_site_mismatch")
    source = create_source_product(
        db,
        source_url=source_url,
        status=SourceProductStatus.NEEDS_MANUAL_ACTION,
        collection_error=(
            "Operator-provided HTML snapshot; ASIN matched but content was not independently fetched."
        ),
        snapshot=parsed,
        collection_method="operator_snapshot",
    )
    variant_asin, variant_attributes = selected_source_variant(parsed, source.asin)
    model = create_product_draft(
        db,
        draft,
        source_product_id=source.id,
        source_variant_asin=variant_asin,
        source_variant_attributes=variant_attributes,
        commit=False,
    )
    if job is not None:
        previous_source_product_id = job.source_product_id
        job.source_product_id = source.id
        job.draft_id = model.id
        job.status = CollectionJobStatus.COMPLETED
        job.message = (
            "Operator HTML snapshot imported; source identity matched but content "
            "was not independently fetched."
        )
        job.completed_at = datetime.now(UTC)
        create_audit_event(
            db=db,
            actor_type="operator",
            actor_id="local-ui",
            action="collection_job.snapshot_resolved",
            entity_type="collection_job",
            entity_id=str(job.id),
            before={
                "status": CollectionJobStatus.NEEDS_MANUAL_ACTION.value,
                "source_product_id": previous_source_product_id,
            },
            after={
                "status": CollectionJobStatus.COMPLETED.value,
                "source_product_id": source.id,
                "draft_id": model.id,
                "collection_method": "operator_snapshot",
            },
            commit=False,
        )
    db.commit()
    return PersistedDraftResponse(id=model.id, draft=draft)


@router.post("/amazon-url", response_model=CollectionResult)
async def import_amazon_url(
    payload: AmazonUrlImport, db: Session = Depends(get_db)
) -> CollectionResult:
    source_url = _normalized_amazon_url_or_422(payload.source_url)
    target_site_id = _target_site_or_422(payload.target_site_id)
    request_time = datetime.now(UTC)
    reservation = reserve_domain_request(
        db,
        source_url,
        now=request_time,
        min_interval_seconds=settings.amazon_domain_min_interval_seconds,
        lease_seconds=settings.job_stale_after_seconds,
    )
    if not reservation.reserved:
        db.commit()
        wait_seconds = max(
            1,
            int((reservation.available_at - request_time).total_seconds()) + 1,
        )
        raise HTTPException(
            status_code=429,
            detail="amazon_domain_throttled",
            headers={"Retry-After": str(wait_seconds)},
        )
    assert reservation.reservation_id is not None
    db.commit()
    result = await collect_amazon_page(source_url, target_site_id)
    record_domain_outcome(
        db,
        source_url,
        outcome=(
            "challenge"
            if result.status.value == "needs_manual_action"
            and result.message.startswith("Amazon challenge detected")
            else result.status.value
        ),
        now=datetime.now(UTC),
        challenge_backoff_base_seconds=settings.amazon_challenge_backoff_base_seconds,
        challenge_backoff_max_seconds=settings.amazon_challenge_backoff_max_seconds,
        min_interval_seconds=settings.amazon_domain_min_interval_seconds,
        reservation_id=reservation.reservation_id,
    )
    db.commit()
    if not payload.persist:
        return result
    status_map = {
        "collected": SourceProductStatus.COLLECTED,
        "needs_manual_action": SourceProductStatus.NEEDS_MANUAL_ACTION,
        "failed": SourceProductStatus.FAILED,
    }
    source = create_source_product(
        db,
        source_url=source_url,
        status=status_map[result.status.value],
        collection_error="" if result.status.value == "collected" else result.message,
        snapshot=result.source_snapshot,
        collection_method=result.collection_method,
    )
    draft_model = None
    if result.draft:
        variant_asin, variant_attributes = selected_source_variant(
            result.source_snapshot, source.asin
        )
        draft_model = create_product_draft(
            db,
            result.draft,
            source_product_id=source.id,
            source_variant_asin=variant_asin,
            source_variant_attributes=variant_attributes,
        )
    else:
        db.commit()
    return result.model_copy(
        update={
            "source_product_id": source.id,
            "draft_id": draft_model.id if draft_model else None,
        }
    )


@router.post("/amazon-url/jobs", response_model=CollectionJobRead)
def create_amazon_url_collection_job(
    payload: AmazonUrlImport, db: Session = Depends(get_db)
) -> CollectionJobRead:
    normalized_url = _normalized_amazon_url_or_422(payload.source_url)
    target_site_id = _target_site_or_422(payload.target_site_id)
    _lock_collection_site(db, target_site_id)
    if existing := _existing_collection_jobs(
        db, target_site_id, {normalized_url}
    ).get(normalized_url):
        return to_collection_job_read(existing)
    job = create_collection_job(
        db=db,
        source_url=normalized_url,
        target_site_id=target_site_id,
    )
    source = db.get(SourceProduct, job.source_product_id) if job.source_product_id else None
    return to_collection_job_read(job, source)


@router.post("/amazon-url/jobs/batch", response_model=CollectionBatchRead)
def create_amazon_url_collection_jobs_batch(
    payload: AmazonUrlBatchImport, db: Session = Depends(get_db)
) -> CollectionBatchRead:
    return _create_amazon_url_collection_jobs_batch(payload, db)


@router.post("/amazon-search/discover", response_model=CollectionBatchRead)
async def discover_amazon_search_products(
    payload: AmazonDiscoveryImport, db: Session = Depends(get_db)
) -> CollectionBatchRead:
    target_site_id = _target_site_or_422(payload.target_site_id)
    try:
        discovered = await discover_amazon_products(payload.domain, payload.keyword, payload.limit)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if discovered.challenge_detected:
        raise HTTPException(status_code=409, detail="amazon_search_challenge_manual_action_required")
    if not discovered.product_urls:
        raise HTTPException(status_code=404, detail="amazon_search_no_products_found")
    return _create_amazon_url_collection_jobs_batch(
        AmazonUrlBatchImport(
            source_urls=discovered.product_urls,
            target_site_id=target_site_id,
            allow_existing=False,
        ),
        db,
    )


@router.post("/amazon-search/campaigns", response_model=KeywordCampaignRead)
def create_keyword_campaign(payload: KeywordCampaignCreate, db: Session = Depends(get_db)) -> KeywordCampaignRead:
    keywords = normalize_keywords(payload.keywords)
    if not keywords:
        raise HTTPException(status_code=422, detail="keyword_campaign_requires_keywords")
    _target_site_or_422(payload.target_site_id)
    row = KeywordCollectionCampaign(name=" ".join(payload.name.split()), domain=payload.domain.strip().lower(),
        target_site_id=payload.target_site_id.upper(), keywords_json=keywords, pages_per_keyword=payload.pages_per_keyword,
        status=KeywordCampaignStatus.PENDING.value, message="等待后台按关键词发现商品。")
    db.add(row)
    db.commit(); db.refresh(row)
    return _campaign_read(row, db)


@router.get("/amazon-search/campaigns", response_model=list[KeywordCampaignRead])
def list_keyword_campaigns(db: Session = Depends(get_db)) -> list[KeywordCampaignRead]:
    return [_campaign_read(row, db) for row in db.query(KeywordCollectionCampaign).order_by(KeywordCollectionCampaign.id.desc()).limit(30).all()]


@router.post("/amazon-url/jobs/file", response_model=CollectionBatchRead)
async def create_amazon_url_collection_jobs_file(
    file: UploadFile = File(...),
    target_site_id: str = Form(default="MLM"),
    allow_existing: bool = Form(default=False),
    db: Session = Depends(get_db),
) -> CollectionBatchRead:
    try:
        source_urls = await run_in_threadpool(
            parse_amazon_url_file,
            file.filename or "",
            await file.read(MAX_IMPORT_FILE_BYTES + 1),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _create_amazon_url_collection_jobs_batch(
        AmazonUrlBatchImport(
            source_urls=source_urls,
            target_site_id=target_site_id,
            allow_existing=allow_existing,
        ),
        db,
    )


def _create_amazon_url_collection_jobs_batch(
    payload: AmazonUrlBatchImport, db: Session
) -> CollectionBatchRead:
    target_site_id = _target_site_or_422(payload.target_site_id)
    existing_by_url: dict[str, CollectionJob] = {}
    if not payload.allow_existing:
        _lock_collection_site(db, target_site_id)
        normalized_candidates = {
            normalized
            for input_url in payload.source_urls
            if (normalized := _try_normalize_amazon_url(input_url)) is not None
        }
        existing_by_url = _existing_collection_jobs(
            db, target_site_id, normalized_candidates
        )

    seen: set[str] = set()
    items: list[CollectionBatchItemRead | None] = []
    entries: list[tuple[int, str]] = []
    for input_url in payload.source_urls:
        try:
            normalized_url = normalize_amazon_product_url(input_url)
        except ValueError as exc:
            items.append(
                CollectionBatchItemRead(
                    input_url=input_url,
                    outcome="invalid",
                    detail=str(exc),
                )
            )
            continue
        if normalized_url in seen:
            items.append(
                CollectionBatchItemRead(
                    input_url=input_url,
                    normalized_url=normalized_url,
                    outcome="duplicate_input",
                    detail="duplicate_amazon_product_in_request",
                )
            )
            continue
        seen.add(normalized_url)
        if existing := existing_by_url.get(normalized_url):
            items.append(
                CollectionBatchItemRead(
                    input_url=input_url,
                    normalized_url=normalized_url,
                    outcome="existing",
                    detail="collection_job_already_exists",
                    job=to_collection_job_read(existing),
                )
            )
            continue
        item_index = len(items)
        items.append(None)
        entries.append((item_index, normalized_url))

    jobs = create_collection_jobs(
        db,
        [(normalized_url, target_site_id) for _, normalized_url in entries],
    ) if entries else []
    for (item_index, normalized_url), job in zip(entries, jobs, strict=True):
        items[item_index] = CollectionBatchItemRead(
            input_url=payload.source_urls[item_index],
            normalized_url=normalized_url,
            outcome="created",
            job=to_collection_job_read(job),
        )

    result_items = [item for item in items if item is not None]
    return CollectionBatchRead(
        created_count=sum(item.outcome == "created" for item in result_items),
        duplicate_count=sum(item.outcome == "duplicate_input" for item in result_items),
        existing_count=sum(item.outcome == "existing" for item in result_items),
        invalid_count=sum(item.outcome == "invalid" for item in result_items),
        items=result_items,
    )


@router.get("/amazon-url/jobs", response_model=list[CollectionJobRead])
def get_amazon_url_collection_jobs(
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    campaign_id: int | None = Query(default=None, ge=1),
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[CollectionJobRead]:
    return list_collection_jobs(db, limit=limit, offset=offset, campaign_id=campaign_id, status=status)


@router.get("/amazon-url/jobs/status", response_model=list[CollectionJobRead])
def get_amazon_url_collection_job_statuses(
    job_ids: list[int] = Query(default=[]),
    db: Session = Depends(get_db),
) -> list[CollectionJobRead]:
    unique_ids = list(dict.fromkeys(job_ids))
    if len(unique_ids) > 200:
        raise HTTPException(status_code=422, detail="collection_job_status_limit_exceeded")
    return list_collection_jobs_by_ids(db, unique_ids)


@router.get("/source-products/{source_product_id}", response_model=SourceProductRead)
def get_source_product(
    source_product_id: int,
    db: Session = Depends(get_db),
) -> SourceProductRead:
    source = db.get(SourceProduct, source_product_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source product not found.")
    return to_source_product_read(source)


@router.post("/amazon-extension/capture")
def create_source_product_from_extension(
    payload: AmazonExtensionCapture,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """Persist a first-time browser-extension capture as a source and draft.

    This is intentionally separate from the re-collection endpoint below: a
    first capture creates one draft, while re-collection only updates drafts
    already bound to the source product.
    """
    source_url = _normalized_amazon_url_or_422(payload.source_url)
    target_site_id = _target_site_or_422(payload.target_site_id)
    raw_snapshot = dict(payload.snapshot)
    video_urls = [
        str(value).strip()
        for value in raw_snapshot.pop("video_urls", [])
        if str(value).strip()
    ]
    try:
        snapshot = AmazonSourceSnapshot.model_validate({**raw_snapshot, "source_url": source_url})
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"invalid_extension_snapshot: {exc}") from exc

    selected_images = select_listing_images(snapshot.images)
    quality = _extension_capture_quality(
        snapshot,
        image_count=len(selected_images),
        video_count=len(video_urls),
    )
    if not snapshot.title.strip() or not selected_images:
        raise HTTPException(
            status_code=422,
            detail={"code": "extension_capture_incomplete", **quality},
        )

    source = create_source_product(
        db,
        source_url=source_url,
        status=SourceProductStatus.COLLECTED,
        snapshot=snapshot,
        collection_method="browser_extension",
    )
    variant_asin, variant_attributes = selected_source_variant(snapshot, source.asin)
    draft_payload = normalize_amazon_product(snapshot.model_dump(), target_site_id)
    draft_payload.video_urls = video_urls
    draft = create_product_draft(
        db,
        draft_payload,
        source_product_id=source.id,
        source_variant_asin=variant_asin,
        source_variant_attributes=variant_attributes,
        commit=False,
    )
    db.commit()
    db.refresh(draft)
    return {
        "ok": True,
        "id": draft.id,
        "draft_id": draft.id,
        "source_product_id": source.id,
        "quality": quality,
    }


@router.post("/source-products/{source_product_id}/extension-capture")
def capture_source_product_from_extension(
    source_product_id: int,
    payload: AmazonExtensionCapture,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    source = db.scalar(select(SourceProduct).where(SourceProduct.id == source_product_id).with_for_update())
    if source is None:
        raise HTTPException(status_code=404, detail="source_product_not_found")
    source_url = _normalized_amazon_url_or_422(payload.source_url)
    if normalize_amazon_product_url(source.source_url) != source_url:
        raise HTTPException(status_code=409, detail="source_product_url_mismatch")
    raw_snapshot = dict(payload.snapshot)
    video_urls = [
        str(value).strip()
        for value in raw_snapshot.pop("video_urls", [])
        if str(value).strip()
    ]
    try:
        snapshot = AmazonSourceSnapshot.model_validate({**raw_snapshot, "source_url": source_url})
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"invalid_extension_snapshot: {exc}") from exc
    source.source_url = source_url
    source.asin = snapshot.source_url.rsplit("/", 1)[-1].upper()
    source.raw_status = SourceProductStatus.COLLECTED
    source.collection_method = "browser_extension"
    source.collected_at = datetime.now(UTC)
    source.collection_error = ""
    source.title = snapshot.title
    source.brand = snapshot.brand
    source.source_price = snapshot.price.amount
    source.source_currency = snapshot.price.currency
    source.description = snapshot.description
    source.bullets_json = snapshot.bullets
    source.image_urls_json = select_listing_images(snapshot.images)
    source.variants_json = [{**variant.model_dump(), "image_urls": select_listing_images(variant.image_urls)} for variant in snapshot.variants]
    source.technical_details_json = snapshot.technical_details
    source.measurements_json = snapshot.measurements.model_dump(exclude_none=True)
    drafts = db.query(ProductDraft).filter(ProductDraft.source_product_id == source.id).all()
    for draft in drafts:
        variant = next((row for row in source.variants_json if str(row.get("asin", "")).upper() == (draft.source_variant_asin or "").upper()), None)
        images = variant.get("image_urls", []) if variant and variant.get("image_urls") else source.image_urls_json
        update_draft_content(db, draft.id, expected_content_version=draft.content_version, image_urls_json=images, video_urls_json=video_urls)
    db.commit()
    return {
        "ok": True,
        "source_product_id": source.id,
        "draft_count": len(drafts),
        "quality": _extension_capture_quality(
            snapshot,
            image_count=len(source.image_urls_json),
            video_count=len(video_urls),
        ),
    }


@router.post(
    "/source-products/{source_product_id}/variants/{variant_asin}/draft",
    response_model=ProductDraftRead,
)
def create_source_variant_product_draft(
    source_product_id: int,
    variant_asin: str,
    payload: SourceVariantDraftCreate,
    db: Session = Depends(get_db),
) -> ProductDraftRead:
    source = db.get(SourceProduct, source_product_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source product not found.")
    target_site_id = _target_site_or_422(payload.target_site_id)
    normalized_asin = variant_asin.strip().upper()
    source_read = to_source_product_read(source)
    snapshot = source_read.snapshot
    if snapshot is None:
        raise HTTPException(status_code=409, detail="source_snapshot_unavailable")
    variant = next(
        (item for item in snapshot.variants if item.asin == normalized_asin),
        None,
    )
    if variant is None:
        raise HTTPException(status_code=404, detail="source_variant_not_found")
    selected_asin, _ = selected_source_variant(snapshot, source.asin)
    if normalized_asin != selected_asin:
        exact_draft = _completed_variant_page_draft(
            db,
            source,
            normalized_asin,
            target_site_id,
        )
        if exact_draft is None:
            raise HTTPException(
                status_code=409,
                detail="variant_page_collection_required",
            )
        return to_draft_read(exact_draft)
    try:
        draft, _ = create_or_get_source_variant_draft(
            db, source, normalized_asin, target_site_id
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return to_draft_read(draft)


def _completed_variant_page_draft(
    db: Session,
    parent_source: SourceProduct,
    variant_asin: str,
    target_site_id: str,
) -> ProductDraft | None:
    normalized_source_url = _normalized_amazon_url_or_422(parent_source.source_url)
    source_parts = urlparse(normalized_source_url)
    variant_url = f"{source_parts.scheme}://{source_parts.netloc}/dp/{variant_asin}"
    return (
        db.query(ProductDraft)
        .join(CollectionJob, CollectionJob.draft_id == ProductDraft.id)
        .join(SourceProduct, CollectionJob.source_product_id == SourceProduct.id)
        .filter(
            CollectionJob.source_identity == variant_url,
            CollectionJob.target_site_id == target_site_id,
            CollectionJob.status == CollectionJobStatus.COMPLETED,
            SourceProduct.raw_status.in_(EXACT_PAGE_EVIDENCE_STATUSES),
            func.upper(SourceProduct.asin) == variant_asin,
            ProductDraft.source_product_id == SourceProduct.id,
            func.upper(ProductDraft.source_variant_asin) == variant_asin,
            ProductDraft.target_site_id == target_site_id,
        )
        .order_by(CollectionJob.id.desc(), ProductDraft.id.desc())
        .first()
    )


@router.post(
    "/source-products/{source_product_id}/variants/{variant_asin}/collection-job",
    response_model=CollectionJobRead,
)
def create_source_variant_collection_job(
    source_product_id: int,
    variant_asin: str,
    payload: SourceVariantCollectionCreate,
    db: Session = Depends(get_db),
) -> CollectionJobRead:
    source = db.get(SourceProduct, source_product_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source product not found.")
    normalized_asin = variant_asin.strip().upper()
    known_asins = {
        str(variant.get("asin", "")).strip().upper()
        for variant in (source.variants_json or [])
        if isinstance(variant, dict)
    }
    if not re.fullmatch(r"[A-Z0-9]{10}", normalized_asin) or normalized_asin not in known_asins:
        raise HTTPException(status_code=404, detail="source_variant_not_found")
    target_site_id = _target_site_or_422(payload.target_site_id)
    normalized_source_url = _normalized_amazon_url_or_422(source.source_url)
    source_parts = urlparse(normalized_source_url)
    variant_url = f"{source_parts.scheme}://{source_parts.netloc}/dp/{normalized_asin}"
    db.rollback()
    _lock_collection_site(db, target_site_id)
    existing = _existing_collection_jobs(db, target_site_id, {variant_url}).get(variant_url)
    if existing is not None:
        existing_source = (
            db.get(SourceProduct, existing.source_product_id)
            if existing.source_product_id is not None
            else None
        )
        return to_collection_job_read(existing, existing_source)
    job = create_collection_job(db, variant_url, target_site_id)
    return to_collection_job_read(job)


@router.post(
    "/source-products/{source_product_id}/variants/collection-jobs",
    response_model=SourceVariantCollectionBatchRead,
)
def create_source_variant_collection_jobs(
    source_product_id: int,
    payload: SourceVariantCollectionCreate,
    db: Session = Depends(get_db),
) -> SourceVariantCollectionBatchRead:
    source = db.get(SourceProduct, source_product_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source product not found.")
    target_site_id = _target_site_or_422(payload.target_site_id)
    normalized_source_url = _normalized_amazon_url_or_422(source.source_url)
    source_parts = urlparse(normalized_source_url)
    selected_source_asin = source.asin.strip().upper()
    selected_by_asin: dict[str, bool] = {}
    for variant in source.variants_json or []:
        if not isinstance(variant, dict):
            continue
        asin = str(variant.get("asin", "")).strip().upper()
        if not re.fullmatch(r"[A-Z0-9]{10}", asin):
            continue
        selected_by_asin[asin] = (
            selected_by_asin.get(asin, False)
            or bool(variant.get("selected"))
            or asin == selected_source_asin
        )
    selected_asins = {asin for asin, selected in selected_by_asin.items() if selected}
    variant_asins = [asin for asin, selected in selected_by_asin.items() if not selected]
    if len(variant_asins) > 100:
        raise HTTPException(status_code=422, detail="source_variant_batch_limit_exceeded")
    variant_urls = [
        f"{source_parts.scheme}://{source_parts.netloc}/dp/{asin}" for asin in variant_asins
    ]
    db.rollback()
    _lock_collection_site(db, target_site_id)
    existing_by_url = _existing_collection_jobs(db, target_site_id, set(variant_urls))
    missing_urls = [url for url in variant_urls if url not in existing_by_url]
    created_jobs = create_collection_jobs(
        db, [(url, target_site_id) for url in missing_urls]
    ) if missing_urls else []
    jobs_by_url = {
        **existing_by_url,
        **{job.source_url: job for job in created_jobs},
    }
    jobs = [to_collection_job_read(jobs_by_url[url]) for url in variant_urls]
    return SourceVariantCollectionBatchRead(
        created_count=len(created_jobs),
        reused_count=len(existing_by_url),
        skipped_selected_count=len(selected_asins),
        jobs=jobs,
    )


@router.post("/amazon-url/jobs/{job_id}/run", response_model=CollectionJobRead)
async def run_amazon_url_collection_job(
    job_id: int, db: Session = Depends(get_db)
) -> CollectionJobRead:
    job = await run_collection_job(
        db=db,
        job_id=job_id,
        collector=collect_amazon_page,
        timeout_seconds=settings.job_execution_timeout_seconds,
        domain_min_interval_seconds=settings.amazon_domain_min_interval_seconds,
        domain_request_lease_seconds=settings.job_stale_after_seconds,
        challenge_backoff_base_seconds=settings.amazon_challenge_backoff_base_seconds,
        challenge_backoff_max_seconds=settings.amazon_challenge_backoff_max_seconds,
    )
    source = db.get(SourceProduct, job.source_product_id) if job.source_product_id else None
    return to_collection_job_read(job, source)


def _normalized_amazon_url_or_422(source_url: str) -> str:
    try:
        return normalize_amazon_product_url(source_url)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _target_site_or_422(site_id: str) -> str:
    normalized = site_id.strip().upper()
    if normalized not in SITE_CURRENCIES:
        raise HTTPException(status_code=422, detail="unsupported_mercado_libre_site")
    return normalized


def _lock_collection_site(db: Session, site_id: str) -> None:
    dialect_name = db.get_bind().dialect.name
    if dialect_name == "postgresql":
        db.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:lock_name))"),
            {"lock_name": f"amazon_collection:{site_id}"},
        )
    elif dialect_name == "sqlite":
        # Serialize the read-then-insert section across SQLite connections.
        db.execute(text("BEGIN IMMEDIATE"))


def _try_normalize_amazon_url(source_url: str) -> str | None:
    try:
        return normalize_amazon_product_url(source_url)
    except ValueError:
        return None


def _existing_collection_jobs(
    db: Session, site_id: str, source_identities: set[str]
) -> dict[str, CollectionJob]:
    if not source_identities:
        return {}
    rows = (
        db.query(CollectionJob)
        .filter(
            CollectionJob.target_site_id == site_id,
            CollectionJob.source_identity.in_(source_identities),
        )
        .order_by(CollectionJob.id.desc())
        .all()
    )
    existing_by_url: dict[str, CollectionJob] = {}
    for row in rows:
        if row.source_identity:
            existing_by_url.setdefault(row.source_identity, row)

    # Legacy rows created before source_identity was introduced are a bounded fallback.
    missing = source_identities - existing_by_url.keys()
    if missing:
        legacy_rows = (
            db.query(CollectionJob)
            .filter(
                func.upper(CollectionJob.target_site_id) == site_id,
                CollectionJob.source_identity.is_(None),
            )
            .order_by(CollectionJob.id.desc())
            .all()
        )
        for row in legacy_rows:
            normalized = _try_normalize_amazon_url(row.source_url)
            if normalized in missing:
                existing_by_url.setdefault(normalized, row)
    return existing_by_url

