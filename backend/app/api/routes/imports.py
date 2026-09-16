from typing import Annotated
from types import SimpleNamespace
from datetime import UTC, datetime, timedelta
import re
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import and_, exists, func, or_, select, text
from sqlalchemy.orm import Session, aliased
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
from app.services.amazon.parser import _extract_measurements
from app.services.amazon.normalizer import normalize_amazon_product
from app.services.amazon.import_file import MAX_IMPORT_FILE_BYTES, parse_amazon_url_file
from app.services.amazon.discovery import build_amazon_search_url, discover_amazon_products
from app.services.amazon.throttle import record_domain_outcome, reserve_domain_request
from app.services.drafts import create_product_draft, to_draft_read, update_draft_content
from app.services.amazon.media import merge_listing_images, select_listing_images, select_product_video_urls
from app.services.audit_events import create_audit_event
from app.services.source_products import (
    EXACT_PAGE_EVIDENCE_STATUSES,
    create_or_get_source_variant_draft,
    create_source_product,
    selected_source_variant,
    to_source_product_read,
)
from app.models.source_product import SourceProduct, SourceProductStatus
from app.models.audit_event import AuditEvent
from app.models.product_draft import ProductDraft
from app.models.cbt_listing_config import CbtListingConfig
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
CONTINUOUS_CAMPAIGN_STATUS = KeywordCampaignStatus.CONTINUOUS.value
CONTINUOUS_QUEUE_LOW_WATERMARK = 50
CONTINUOUS_QUEUE_REFILL_SIZE = 200
CONTINUOUS_FAILURE_PAUSE_WINDOW = 10
RECOLLECT_COLLECTOR_KIND = "browser_recollect"
SEARCH_COLLECTOR_KIND = "browser_search"
EXTENSION_COLLECTOR_KIND = "browser_extension"
AMAZON_BROWSER_COLLECTOR_KINDS = (
    EXTENSION_COLLECTOR_KIND,
    RECOLLECT_COLLECTOR_KIND,
    SEARCH_COLLECTOR_KIND,
)
CONTINUOUS_SEARCH_PAGE_SPAN = 7
CONTINUOUS_SEARCH_SORTS = ("", "price-asc-rank", "review-rank", "date-desc-rank")


def _source_has_deleted_draft(db: Session, source_product_id: int) -> bool:
    """Return whether this source has an operator deletion tombstone.

    Audit JSON is intentionally inspected in Python for SQLite/PostgreSQL
    parity. The event set is small and deletion history is authoritative.
    """
    rows = db.query(AuditEvent.before_json).filter(AuditEvent.action == "draft.deleted").all()
    return any(
        isinstance(before, dict)
        and str(before.get("source_product_id") or "") == str(source_product_id)
        for (before,) in rows
    )


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
    collector_kind: str = Field(default="server", pattern="^(server|browser_extension)$")


class AmazonExtensionCapture(BaseModel):
    source_url: AmazonProductUrl
    target_site_id: str = "CBT"
    snapshot: dict = Field(default_factory=dict)


class AmazonExtensionJobResult(BaseModel):
    worker_id: str = Field(min_length=1, max_length=120)
    source_url: AmazonProductUrl
    status: str = Field(default="collected", pattern="^(collected|needs_manual_action|failed)$")
    message: str = Field(default="", max_length=2000)
    snapshot: dict = Field(default_factory=dict)
    product_urls: list[AmazonProductUrl] = Field(default_factory=list, max_length=100)


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


_UNBRANDED_SOURCE_VALUES = {
    "",
    "does not apply",
    "generic",
    "generico",
    "genérico",
    "no brand",
    "none",
    "not branded",
    "not applicable",
    "n/a",
    "sans marque",
    "sem marca",
    "sin marca",
    "unknown",
    "unbranded",
    "without brand",
}

_GENERIC_AUTOMATED_TITLE_OPENERS = {
    "adjustable", "adhesive", "baking", "bathtub", "bowl", "cake", "coat",
    "cupcake", "digital", "document", "door", "dough", "drawer", "furniture",
    "handheld", "heavy", "kitchen", "large", "magnetic", "measuring", "metal",
    "mini", "mixing", "non-slip", "nonstick", "oven", "pack", "piece", "pieces",
    "plastic", "professional", "remote", "reusable", "scraper", "set", "silicone",
    "sink", "small", "soap", "stainless", "steel", "toothbrush", "towel",
    "universal", "wall", "wood", "wooden",
}


def _automated_discovery_brand(
    snapshot: AmazonSourceSnapshot, campaign_keyword: str | None = None
) -> tuple[str, str]:
    """Return a real source brand that should exclude an automated candidate.

    Amazon search cards do not expose a dependable brand field, so the safe
    decision point is the completed detail-page capture.  This rule is scoped
    to overnight keyword campaign jobs; operator collection and recollection
    must keep working even when Amazon reports a brand.
    """
    brand = " ".join(str(snapshot.brand or "").split()).strip()
    normalized = re.sub(r"^(?:brand|brand name|marca)\s*:\s*", "", brand, flags=re.IGNORECASE)
    normalized = normalized.strip(" .,:;-/").casefold()
    if normalized not in _UNBRANDED_SOURCE_VALUES:
        return brand, "source_brand_present"

    # Amazon sometimes renders the byline late or returns "Generic" even when
    # the title still begins with a clear brand (for example OXO, KitchenAid or
    # Ovenza).  For unattended selection, use a conservative title fallback:
    # accept numeric/generic product openers and the campaign's own product
    # words; otherwise treat the leading token as suspected brand evidence.
    title = " ".join(str(snapshot.title or "").split()).strip()
    match = re.match(r"^([A-Za-z0-9][A-Za-z0-9&'+.-]*)", title)
    if not match:
        return "", ""
    opener = match.group(1)
    opener_key = opener.strip(" .,:;-/").casefold()
    keyword_tokens = {
        token.casefold()
        for token in re.findall(r"[A-Za-z0-9]+", campaign_keyword or "")
    }
    if (
        opener_key[:1].isdigit()
        or opener_key in keyword_tokens
        or opener_key in _GENERIC_AUTOMATED_TITLE_OPENERS
    ):
        return "", ""
    return opener, "title_brand_suspected"


def _is_automated_brand_filtered_job(job: CollectionJob) -> bool:
    return (
        job.status == CollectionJobStatus.SKIPPED
        and job.message.startswith("自动选品已跳过品牌商品：")
    )


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
    bound_worker_id: str | None = None
    bound_browser_name: str | None = None
    bound_browser_version: str | None = None
    bound_extension_version: str | None = None
    keywords: list[dict[str, int | str]] = []


class ExtensionContinuousControl(BaseModel):
    worker_id: str = Field(min_length=1, max_length=120)
    browser_name: str = Field(min_length=1, max_length=80)
    browser_version: str = Field(default="", max_length=40)
    extension_version: str = Field(min_length=1, max_length=40)
    campaign_id: int | None = Field(default=None, ge=1)


class RecollectFailure(BaseModel):
    message: str = Field(default="上架库补采插件未返回有效结果。", max_length=500)


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
            "skipped": 0,
        }
        for keyword in keywords
    }
    for keyword, status, count in progress_rows:
        if not keyword:
            continue
        item = progress.setdefault(keyword, {"keyword": keyword, "discovered": 0, "completed": 0, "running": 0, "pending": 0, "failed": 0, "needs_manual_action": 0, "skipped": 0})
        item["discovered"] = int(item["discovered"]) + int(count)
        if status in item:
            item[status] = int(item[status]) + int(count)
    for item in progress.values():
        item["processed"] = int(item["completed"]) + int(item["failed"]) + int(item["needs_manual_action"]) + int(item["skipped"])
        item["status"] = "处理中" if int(item["running"]) else ("待处理" if int(item["pending"]) else ("已完成" if int(item["processed"]) else "未发现结果"))
    return KeywordCampaignRead(id=row.id, name=row.name, domain=row.domain, target_site_id=row.target_site_id,
        keyword_count=len(keywords), pages_per_keyword=row.pages_per_keyword, status=row.status,
        current_keyword=current, current_page=row.current_page, discovered_count=row.discovered_count,
        queued_count=row.queued_count, duplicate_count=row.duplicate_count, message=row.message,
        bound_worker_id=row.bound_worker_id, bound_browser_name=row.bound_browser_name,
        bound_browser_version=row.bound_browser_version, bound_extension_version=row.bound_extension_version,
        keywords=list(progress.values()))


def _preferred_extension_campaign(
    campaigns: list[KeywordCollectionCampaign],
) -> KeywordCollectionCampaign | None:
    """Pick the endless campaign instead of an unrelated newer one-off batch."""
    eligible = [row for row in campaigns if row.keywords_json]
    return max(
        eligible,
        key=lambda row: (
            3 if row.status == CONTINUOUS_CAMPAIGN_STATUS else 0,
            2
            if row.status == KeywordCampaignStatus.PAUSED.value
            and (int(row.discovered_count or 0) > 0 or int(row.queued_count or 0) > 0)
            else 0,
            row.id,
        ),
        default=None,
    )


def _continuous_search_position(campaign: KeywordCollectionCampaign) -> tuple[int, int, str, str]:
    """Return the durable cursor and local-browser search URL for an endless campaign."""
    keywords = campaign.keywords_json or []
    if not keywords:
        raise ValueError("keyword_campaign_requires_keywords")
    keyword_index = max(0, int(campaign.current_keyword_index or 0))
    virtual_page = max(1, int(campaign.current_page or 1))
    if keyword_index >= len(keywords):
        keyword_index = 0
        virtual_page += 1
    keyword = keywords[keyword_index]
    actual_page = ((virtual_page - 1) % CONTINUOUS_SEARCH_PAGE_SPAN) + 1
    sort_index = ((virtual_page - 1) // CONTINUOUS_SEARCH_PAGE_SPAN) % len(CONTINUOUS_SEARCH_SORTS)
    search_url = build_amazon_search_url(campaign.domain, keyword, actual_page)
    sort_value = CONTINUOUS_SEARCH_SORTS[sort_index]
    if sort_value:
        search_url = f"{search_url}&s={sort_value}"
    return keyword_index, virtual_page, keyword, search_url


def _advance_continuous_search_cursor(campaign: KeywordCollectionCampaign) -> None:
    keywords = campaign.keywords_json or []
    if not keywords:
        return
    keyword_index = max(0, int(campaign.current_keyword_index or 0))
    virtual_page = max(1, int(campaign.current_page or 1))
    if keyword_index >= len(keywords):
        keyword_index = 0
        virtual_page += 1
    keyword_index += 1
    if keyword_index >= len(keywords):
        keyword_index = 0
        virtual_page += 1
    campaign.current_keyword_index = keyword_index
    campaign.current_page = virtual_page


def _maintain_continuous_extension_queue(db: Session) -> None:
    """Refill the active unattended campaign before the extension goes idle."""
    campaigns = (
        db.query(KeywordCollectionCampaign)
        .filter(KeywordCollectionCampaign.status == CONTINUOUS_CAMPAIGN_STATUS)
        .order_by(KeywordCollectionCampaign.id.desc())
        .all()
    )
    if not campaigns:
        return
    campaign = campaigns[0]
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:name))"), {"name": "amazon_continuous_campaign_refill"})
        campaigns = (
            db.query(KeywordCollectionCampaign)
            .filter(KeywordCollectionCampaign.status == CONTINUOUS_CAMPAIGN_STATUS)
            .order_by(KeywordCollectionCampaign.id.desc())
            .with_for_update()
            .all()
        )
        if not campaigns:
            db.commit()
            return
        campaign = campaigns[0]
    for older in campaigns[1:]:
        older.status = KeywordCampaignStatus.PAUSED.value
        older.message = f"已有更新的持续挂机任务 #{campaign.id}，本任务已自动暂停。"
        create_audit_event(
            db,
            actor_type="system",
            actor_id="continuous-collection-guard",
            action="keyword_campaign.continuous_superseded",
            entity_type="keyword_campaign",
            entity_id=str(older.id),
            after={"new_active_campaign_id": campaign.id},
            commit=False,
        )

    recent_terminal = (
        db.query(CollectionJob)
        .filter(
            CollectionJob.campaign_id == campaign.id,
            CollectionJob.collector_kind.in_(AMAZON_BROWSER_COLLECTOR_KINDS),
            CollectionJob.status.in_([
                CollectionJobStatus.COMPLETED,
                CollectionJobStatus.SKIPPED,
                CollectionJobStatus.FAILED,
                CollectionJobStatus.NEEDS_MANUAL_ACTION,
            ]),
        )
        .order_by(CollectionJob.completed_at.desc(), CollectionJob.id.desc())
        .limit(CONTINUOUS_FAILURE_PAUSE_WINDOW)
        .all()
    )
    if (
        len(recent_terminal) == CONTINUOUS_FAILURE_PAUSE_WINDOW
        and all(
            job.status in {CollectionJobStatus.FAILED, CollectionJobStatus.NEEDS_MANUAL_ACTION}
            for job in recent_terminal
        )
    ):
        campaign.status = KeywordCampaignStatus.PAUSED.value
        campaign.message = "浏览器插件连续 10 个任务失败或需要验证，持续挂机已自动暂停。"
        create_audit_event(
            db,
            actor_type="system",
            actor_id="continuous-collection-guard",
            action="keyword_campaign.continuous_auto_paused",
            entity_type="keyword_campaign",
            entity_id=str(campaign.id),
            after={"reason": "consecutive_collection_failures", "window": CONTINUOUS_FAILURE_PAUSE_WINDOW},
            commit=False,
        )
        db.commit()
        return

    queued = (
        db.query(func.count(CollectionJob.id))
        .filter(
            CollectionJob.campaign_id == campaign.id,
            CollectionJob.collector_kind.in_([EXTENSION_COLLECTOR_KIND, RECOLLECT_COLLECTOR_KIND]),
            CollectionJob.status.in_([CollectionJobStatus.PENDING, CollectionJobStatus.RUNNING]),
        )
        .scalar()
        or 0
    )
    if queued >= CONTINUOUS_QUEUE_LOW_WATERMARK:
        db.commit()
        return

    browser_job = aliased(CollectionJob)
    pool_rows = (
        db.query(CollectionJob)
        .filter(
            CollectionJob.collector_kind == "server",
            CollectionJob.target_site_id == campaign.target_site_id,
            CollectionJob.status == CollectionJobStatus.FAILED,
            CollectionJob.campaign_keyword.in_(campaign.keywords_json or []),
            ~exists().where(
                (browser_job.collector_kind.in_(["browser_extension", RECOLLECT_COLLECTOR_KIND]))
                & (browser_job.target_site_id == CollectionJob.target_site_id)
                & (browser_job.source_identity == CollectionJob.source_identity)
            ),
        )
        .order_by(CollectionJob.id.asc())
        .limit(CONTINUOUS_QUEUE_REFILL_SIZE * 4)
        .all()
    )
    seen: set[str] = set()
    selected: list[CollectionJob] = []
    for row in pool_rows:
        identity = str(row.source_identity or row.source_url)
        if identity in seen:
            continue
        seen.add(identity)
        selected.append(row)
        if len(selected) >= CONTINUOUS_QUEUE_REFILL_SIZE:
            break
    if not selected:
        search_exists = (
            db.query(CollectionJob.id)
            .filter(
                CollectionJob.campaign_id == campaign.id,
                CollectionJob.collector_kind == SEARCH_COLLECTOR_KIND,
                CollectionJob.status.in_([CollectionJobStatus.PENDING, CollectionJobStatus.RUNNING]),
            )
            .first()
        )
        if search_exists is not None:
            db.commit()
            return
        try:
            keyword_index, virtual_page, keyword, search_url = _continuous_search_position(campaign)
        except ValueError:
            campaign.status = KeywordCampaignStatus.PAUSED.value
            campaign.message = "持续采集缺少关键词，已自动暂停。"
            db.commit()
            return
        campaign.current_keyword_index = keyword_index
        campaign.current_page = virtual_page
        search_job = CollectionJob(
            source_url=search_url,
            source_identity=f"continuous-search:{campaign.id}:{virtual_page}:{keyword_index}",
            target_site_id=campaign.target_site_id,
            campaign_id=campaign.id,
            campaign_keyword=keyword,
            collector_kind=SEARCH_COLLECTOR_KIND,
            message="等待本机插件发现 Amazon 搜索结果。",
        )
        db.add(search_job)
        db.flush()
        create_audit_event(
            db,
            actor_type="system",
            actor_id="continuous-search-refill",
            action="collection_job.created",
            entity_type="collection_job",
            entity_id=str(search_job.id),
            after={
                "status": CollectionJobStatus.PENDING.value,
                "campaign_id": campaign.id,
                "campaign_keyword": keyword,
                "virtual_page": virtual_page,
                "collector_kind": SEARCH_COLLECTOR_KIND,
                "reason": "continuous_local_search_discovery",
            },
            commit=False,
        )
        campaign.message = (
            f"持续采集运行中；本机插件正在发现“{keyword}”第 {virtual_page} 轮候选，"
            "不会因当前候选池为空而结束。"
        )
        db.commit()
        return

    jobs = [
        CollectionJob(
            source_url=row.source_url,
            source_identity=row.source_identity or row.source_url,
            target_site_id=row.target_site_id,
            campaign_id=campaign.id,
            campaign_keyword=row.campaign_keyword,
            collector_kind=EXTENSION_COLLECTOR_KIND,
        )
        for row in selected
    ]
    db.add_all(jobs)
    db.flush()
    for job in jobs:
        create_audit_event(
            db,
            actor_type="system",
            actor_id="continuous-collection-refill",
            action="collection_job.created",
            entity_type="collection_job",
            entity_id=str(job.id),
            after={
                "status": CollectionJobStatus.PENDING.value,
                "source_url": job.source_url,
                "target_site_id": job.target_site_id,
                "campaign_id": campaign.id,
                "campaign_keyword": job.campaign_keyword,
                "collector_kind": job.collector_kind,
                "reason": "continuous_queue_refill",
            },
            commit=False,
        )
    campaign.queued_count += len(jobs)
    campaign.discovered_count += len(jobs)
    campaign.message = f"持续挂机运行中；队列低于 {CONTINUOUS_QUEUE_LOW_WATERMARK} 后自动补入 {len(jobs)} 个候选。"
    create_audit_event(
        db,
        actor_type="system",
        actor_id="continuous-collection-refill",
        action="keyword_campaign.continuous_refilled",
        entity_type="keyword_campaign",
        entity_id=str(campaign.id),
        after={"refilled": len(jobs), "queued_before": queued, "low_watermark": CONTINUOUS_QUEUE_LOW_WATERMARK},
        commit=False,
    )
    db.commit()


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
        # A brand-filtered campaign result is terminal only for automatic
        # selection.  It must not prevent an operator from explicitly asking
        # to collect the same Amazon page later.
        if not _is_automated_brand_filtered_job(existing):
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
    db.commit()
    db.refresh(row)
    return _campaign_read(row, db)


@router.get("/amazon-search/campaigns", response_model=list[KeywordCampaignRead])
def list_keyword_campaigns(db: Session = Depends(get_db)) -> list[KeywordCampaignRead]:
    return [_campaign_read(row, db) for row in db.query(KeywordCollectionCampaign).order_by(KeywordCollectionCampaign.id.desc()).limit(30).all()]


@router.get("/amazon-search/extension-control/status")
def extension_continuous_status(
    worker_id: str = Query(..., min_length=1, max_length=120),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    campaign = _preferred_extension_campaign(db.query(KeywordCollectionCampaign).all())
    if campaign is None:
        return {"active": False, "owns_active": False, "campaign": None}
    return {
        "active": campaign.status == CONTINUOUS_CAMPAIGN_STATUS,
        "owns_active": (
            campaign.status == CONTINUOUS_CAMPAIGN_STATUS
            and campaign.bound_worker_id == worker_id.strip()
        ),
        "campaign": {
            "id": campaign.id,
            "name": campaign.name,
            "status": campaign.status,
            "message": campaign.message,
            "bound_worker_id": campaign.bound_worker_id,
            "bound_browser_name": campaign.bound_browser_name,
            "bound_browser_version": campaign.bound_browser_version,
            "bound_extension_version": campaign.bound_extension_version,
        },
    }


@router.post("/amazon-search/extension-control/start", response_model=KeywordCampaignRead)
def start_extension_continuous_campaign(
    payload: ExtensionContinuousControl,
    db: Session = Depends(get_db),
) -> KeywordCampaignRead:
    campaigns = db.query(KeywordCollectionCampaign).with_for_update().all()
    campaign = next(
        (
            row
            for row in campaigns
            if payload.campaign_id is not None and row.id == payload.campaign_id
        ),
        None,
    )
    if payload.campaign_id is None:
        campaign = _preferred_extension_campaign(campaigns)
    if campaign is None:
        raise HTTPException(status_code=404, detail="keyword_campaign_not_found")
    for row in campaigns:
        if row.id != campaign.id and row.status == CONTINUOUS_CAMPAIGN_STATUS:
            row.status = KeywordCampaignStatus.PAUSED.value
            row.message = f"已由持续挂机任务 #{campaign.id} 接替。"
    before = {
        "status": campaign.status,
        "bound_worker_id": campaign.bound_worker_id,
        "bound_browser_name": campaign.bound_browser_name,
    }
    campaign.status = CONTINUOUS_CAMPAIGN_STATUS
    campaign.bound_worker_id = payload.worker_id.strip()
    campaign.bound_browser_name = payload.browser_name.strip()
    campaign.bound_browser_version = payload.browser_version.strip() or None
    campaign.bound_extension_version = payload.extension_version.strip()
    campaign.bound_at = datetime.now(UTC)
    if campaign.keywords_json and campaign.current_keyword_index >= len(campaign.keywords_json):
        campaign.current_keyword_index = 0
        campaign.current_page = max(1, int(campaign.current_page or 1)) + 1
    browser_label = campaign.bound_browser_name
    if campaign.bound_browser_version:
        browser_label = f"{browser_label} {campaign.bound_browser_version}"
    campaign.message = f"持续筛选采集已绑定到 {browser_label}；仅该插件实例可以领取任务。"
    create_audit_event(
        db,
        actor_type="extension",
        actor_id=payload.worker_id.strip(),
        action="keyword_campaign.extension_continuous_started",
        entity_type="keyword_campaign",
        entity_id=str(campaign.id),
        before=before,
        after={
            "status": campaign.status,
            "browser_name": campaign.bound_browser_name,
            "browser_version": campaign.bound_browser_version,
            "extension_version": campaign.bound_extension_version,
            "worker_id": campaign.bound_worker_id,
            "unbounded": True,
        },
        commit=False,
    )
    db.commit()
    db.refresh(campaign)
    return _campaign_read(campaign, db)


@router.post("/amazon-search/extension-control/stop")
def stop_extension_continuous_campaign(
    payload: ExtensionContinuousControl,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    query = db.query(KeywordCollectionCampaign)
    if payload.campaign_id is not None:
        query = query.filter(KeywordCollectionCampaign.id == payload.campaign_id)
    campaigns = query.with_for_update().all()
    campaign = (
        campaigns[0]
        if payload.campaign_id is not None and campaigns
        else _preferred_extension_campaign(campaigns)
    )
    if campaign is None:
        raise HTTPException(status_code=404, detail="keyword_campaign_not_found")
    if (
        campaign.status == CONTINUOUS_CAMPAIGN_STATUS
        and campaign.bound_worker_id
        and campaign.bound_worker_id != payload.worker_id.strip()
    ):
        raise HTTPException(
            status_code=409,
            detail=f"continuous_campaign_owned_by_{campaign.bound_browser_name or 'another_browser'}",
        )
    before = {
        "status": campaign.status,
        "bound_worker_id": campaign.bound_worker_id,
        "bound_browser_name": campaign.bound_browser_name,
    }
    campaign.status = KeywordCampaignStatus.PAUSED.value
    campaign.message = (
        f"持续筛选采集已由 {payload.browser_name.strip()} 停止；当前任务允许收尾，不再领取新任务。"
    )
    create_audit_event(
        db,
        actor_type="extension",
        actor_id=payload.worker_id.strip(),
        action="keyword_campaign.extension_continuous_stopped",
        entity_type="keyword_campaign",
        entity_id=str(campaign.id),
        before=before,
        after={"status": campaign.status, "browser_name": payload.browser_name.strip()},
        commit=False,
    )
    db.commit()
    return {"ok": True, "campaign_id": campaign.id, "status": campaign.status, "message": campaign.message}


@router.post("/amazon-search/campaigns/{campaign_id}/continuous", response_model=KeywordCampaignRead)
def start_continuous_keyword_campaign(campaign_id: int, db: Session = Depends(get_db)) -> KeywordCampaignRead:
    campaigns = db.query(KeywordCollectionCampaign).with_for_update().all()
    campaign = next((row for row in campaigns if row.id == campaign_id), None)
    if campaign is None:
        raise HTTPException(status_code=404, detail="keyword_campaign_not_found")
    for row in campaigns:
        if row.id != campaign.id and row.status == CONTINUOUS_CAMPAIGN_STATUS:
            row.status = KeywordCampaignStatus.PAUSED.value
            row.message = f"已由持续挂机任务 #{campaign.id} 接替。"
    campaign.status = CONTINUOUS_CAMPAIGN_STATUS
    campaign.bound_worker_id = None
    campaign.bound_browser_name = None
    campaign.bound_browser_version = None
    campaign.bound_extension_version = None
    campaign.bound_at = None
    if campaign.keywords_json and campaign.current_keyword_index >= len(campaign.keywords_json):
        campaign.current_keyword_index = 0
        campaign.current_page = max(1, int(campaign.current_page or 1)) + 1
    campaign.message = "持续采集已启用；本机插件将循环发现搜索结果并去重，不设总量上限。"
    create_audit_event(
        db,
        actor_type="operator",
        actor_id="web",
        action="keyword_campaign.continuous_enabled",
        entity_type="keyword_campaign",
        entity_id=str(campaign.id),
        after={
            "status": CONTINUOUS_CAMPAIGN_STATUS,
            "protocol": "browser_extension_first_capture",
            "discovery_protocol": "local_extension_amazon_search",
            "unbounded": True,
            "converted_pending_jobs": 0,
        },
        commit=False,
    )
    db.commit()
    db.refresh(campaign)
    return _campaign_read(campaign, db)


@router.post("/amazon-search/campaigns/{campaign_id}/pause", response_model=KeywordCampaignRead)
def pause_keyword_campaign(campaign_id: int, db: Session = Depends(get_db)) -> KeywordCampaignRead:
    campaign = db.query(KeywordCollectionCampaign).filter(KeywordCollectionCampaign.id == campaign_id).with_for_update().one_or_none()
    if campaign is None:
        raise HTTPException(status_code=404, detail="keyword_campaign_not_found")
    before = campaign.status
    campaign.status = KeywordCampaignStatus.PAUSED.value
    campaign.message = "持续挂机已由操作员暂停。"
    create_audit_event(
        db,
        actor_type="operator",
        actor_id="web",
        action="keyword_campaign.paused",
        entity_type="keyword_campaign",
        entity_id=str(campaign.id),
        before={"status": before},
        after={"status": campaign.status},
        commit=False,
    )
    db.commit()
    db.refresh(campaign)
    return _campaign_read(campaign, db)


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
        if (
            (existing := existing_by_url.get(normalized_url))
            and not _is_automated_brand_filtered_job(existing)
        ):
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
        collector_kind=payload.collector_kind,
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


@router.get("/amazon-recollect/next")
def claim_next_listing_recollect_job(
    worker_id: str = Query(..., min_length=1, max_length=120),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """Claim one job for the exact same event flow as the listing-library green collect button."""
    _maintain_continuous_extension_queue(db)
    if db.get_bind().dialect.name == "postgresql":
        db.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:name))"),
            {"name": "amazon_browser_global_claim"},
        )
    now = datetime.now(UTC)
    stale_before = now - timedelta(seconds=settings.job_stale_after_seconds)
    stale_jobs = (
        db.query(CollectionJob)
        .filter(
            CollectionJob.collector_kind == RECOLLECT_COLLECTOR_KIND,
            CollectionJob.status == CollectionJobStatus.RUNNING,
            CollectionJob.claimed_at.is_not(None),
            CollectionJob.claimed_at < stale_before,
        )
        .all()
    )
    for stale in stale_jobs:
        stale.status = CollectionJobStatus.PENDING
        stale.message = "上架库补采页面中断，已自动放回队列。"
        stale.started_at = None
        stale.completed_at = None
        stale.claimed_by = None
        stale.claimed_at = None
        create_audit_event(
            db,
            actor_type="system",
            actor_id="listing-recollect-driver",
            action="collection_job.listing_recollect_claim_expired",
            entity_type="collection_job",
            entity_id=str(stale.id),
            after={"status": CollectionJobStatus.PENDING.value},
            commit=False,
        )
    active_job = (
        db.query(CollectionJob.id)
        .filter(
            CollectionJob.collector_kind.in_(AMAZON_BROWSER_COLLECTOR_KINDS),
            CollectionJob.status == CollectionJobStatus.RUNNING,
        )
        .first()
    )
    if active_job is not None:
        db.commit()
        return {"job": None}
    query = (
        db.query(CollectionJob)
        .filter(
            CollectionJob.status == CollectionJobStatus.PENDING,
            CollectionJob.collector_kind == RECOLLECT_COLLECTOR_KIND,
            or_(CollectionJob.next_attempt_at.is_(None), CollectionJob.next_attempt_at <= now),
            or_(
                CollectionJob.campaign_id.is_(None),
                ~CollectionJob.campaign_id.in_(
                    select(KeywordCollectionCampaign.id).where(
                        KeywordCollectionCampaign.status == KeywordCampaignStatus.PAUSED.value
                    )
                ),
            ),
        )
        .order_by(CollectionJob.id.asc())
    )
    if db.get_bind().dialect.name == "postgresql":
        query = query.with_for_update(skip_locked=True)
    job = query.first()
    if job is None:
        db.commit()
        return {"job": None}

    source_url = _normalized_amazon_url_or_422(job.source_url)
    source = db.get(SourceProduct, job.source_product_id) if job.source_product_id else None
    if source is None:
        source = db.scalar(
            select(SourceProduct)
            .where(SourceProduct.source_url == source_url)
            .order_by(SourceProduct.id.asc())
            .limit(1)
        )
    if source is None:
        source = SourceProduct(
            source_url=source_url,
            asin=source_url.rsplit("/", 1)[-1].upper(),
            raw_status=SourceProductStatus.PENDING,
            collection_method="browser_extension",
            source="amazon",
        )
        db.add(source)
        db.flush()

    job.source_product_id = source.id
    job.status = CollectionJobStatus.RUNNING
    job.started_at = now
    job.completed_at = None
    job.claimed_by = worker_id.strip()
    job.claimed_at = now
    job.message = "正在复用上架库绿色“采”流程补采。"
    create_audit_event(
        db,
        actor_type="extension",
        actor_id=worker_id.strip(),
        action="collection_job.listing_recollect_claimed",
        entity_type="collection_job",
        entity_id=str(job.id),
        before={"status": CollectionJobStatus.PENDING.value},
        after={
            "status": CollectionJobStatus.RUNNING.value,
            "source_product_id": source.id,
            "source_url": source_url,
            "protocol": "meli-amazon-recollect",
        },
        commit=False,
    )
    db.commit()
    return {
        "job": {
            "id": job.id,
            "sourceProductId": source.id,
            "sourceUrl": source_url,
            "campaignId": job.campaign_id,
        }
    }


@router.post("/amazon-recollect/jobs/{job_id}/failure")
def fail_listing_recollect_job(
    job_id: int,
    payload: RecollectFailure,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    job = db.scalar(select(CollectionJob).where(CollectionJob.id == job_id).with_for_update())
    if job is None:
        raise HTTPException(status_code=404, detail="collection_job_not_found")
    if job.status in {CollectionJobStatus.COMPLETED, CollectionJobStatus.SKIPPED}:
        return {"ok": True, "job_id": job.id, "status": job.status.value, "idempotent": True}
    if job.collector_kind != RECOLLECT_COLLECTOR_KIND:
        raise HTTPException(status_code=409, detail="collection_job_not_listing_recollect")
    before = job.status.value
    job.status = CollectionJobStatus.FAILED
    job.message = payload.message.strip() or "上架库补采插件未返回有效结果。"
    job.completed_at = datetime.now(UTC)
    job.claimed_by = None
    job.claimed_at = None
    create_audit_event(
        db,
        actor_type="extension",
        actor_id="listing-recollect-driver",
        action="collection_job.listing_recollect_failed",
        entity_type="collection_job",
        entity_id=str(job.id),
        before={"status": before},
        after={"status": job.status.value, "message": job.message},
        commit=False,
    )
    db.commit()
    return {"ok": True, "job_id": job.id, "status": job.status.value}


@router.get("/amazon-extension/next")
def claim_next_amazon_extension_job(
    worker_id: str = Query(..., min_length=1, max_length=120),
    continuous_enabled: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """Atomically give the local browser extension one CBT Amazon job.

    This endpoint deliberately claims only pending jobs. Failed/manual jobs
    require an explicit retry, so an overnight browser cannot create a hot
    retry loop against Amazon.
    """
    _maintain_continuous_extension_queue(db)
    if db.get_bind().dialect.name == "postgresql":
        db.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:name))"),
            {"name": "amazon_browser_global_claim"},
        )
    now = datetime.now(UTC)
    stale_before = now - timedelta(seconds=settings.job_stale_after_seconds)
    stale_jobs = (
        db.query(CollectionJob)
        .filter(
            CollectionJob.status == CollectionJobStatus.RUNNING,
            CollectionJob.collector_kind.in_([EXTENSION_COLLECTOR_KIND, SEARCH_COLLECTOR_KIND]),
            CollectionJob.claimed_by.is_not(None),
            CollectionJob.claimed_at.is_not(None),
            CollectionJob.claimed_at < stale_before,
        )
        .all()
    )
    for stale in stale_jobs:
        stale.status = CollectionJobStatus.PENDING
        stale.message = "浏览器插件连接中断，已自动放回队列。"
        stale.started_at = None
        stale.completed_at = None
        stale.claimed_by = None
        stale.claimed_at = None
        create_audit_event(
            db,
            actor_type="system",
            actor_id="amazon-extension",
            action="collection_job.extension_claim_expired",
            entity_type="collection_job",
            entity_id=str(stale.id),
            before={"status": CollectionJobStatus.RUNNING.value},
            after={"status": CollectionJobStatus.PENDING.value, "message": stale.message},
            commit=False,
        )
    active_job = (
        db.query(CollectionJob.id)
        .filter(
            CollectionJob.collector_kind.in_(AMAZON_BROWSER_COLLECTOR_KINDS),
            CollectionJob.status == CollectionJobStatus.RUNNING,
        )
        .first()
    )
    if active_job is not None:
        db.commit()
        return {"job": None}
    query = (
        db.query(CollectionJob)
        .filter(
            CollectionJob.status == CollectionJobStatus.PENDING,
            CollectionJob.collector_kind.in_([EXTENSION_COLLECTOR_KIND, SEARCH_COLLECTOR_KIND]),
            or_(CollectionJob.next_attempt_at.is_(None), CollectionJob.next_attempt_at <= now),
            or_(
                CollectionJob.campaign_id.is_(None),
                CollectionJob.campaign_id.in_(
                    select(KeywordCollectionCampaign.id).where(
                        KeywordCollectionCampaign.status.not_in(
                            [KeywordCampaignStatus.PAUSED.value, CONTINUOUS_CAMPAIGN_STATUS]
                        )
                    )
                ),
                and_(
                    continuous_enabled,
                    CollectionJob.campaign_id.in_(
                        select(KeywordCollectionCampaign.id).where(
                            KeywordCollectionCampaign.status == CONTINUOUS_CAMPAIGN_STATUS,
                            or_(
                                KeywordCollectionCampaign.bound_worker_id.is_(None),
                                KeywordCollectionCampaign.bound_worker_id == worker_id.strip(),
                            ),
                        )
                    ),
                ),
            ),
        )
        .order_by(CollectionJob.id.asc())
    )
    if db.get_bind().dialect.name == "postgresql":
        query = query.with_for_update(skip_locked=True)
    job = query.first()
    if job is None:
        db.commit()
        return {"job": None}
    job.status = CollectionJobStatus.RUNNING
    job.started_at = now
    job.completed_at = None
    job.next_attempt_at = None
    job.claimed_by = worker_id.strip()
    job.claimed_at = now
    job.message = "本机浏览器插件采集中。"
    create_audit_event(
        db,
        actor_type="extension",
        actor_id=worker_id.strip(),
        action="collection_job.extension_claimed",
        entity_type="collection_job",
        entity_id=str(job.id),
        before={"status": CollectionJobStatus.PENDING.value},
        after={"status": CollectionJobStatus.RUNNING.value, "source_url": job.source_url},
        commit=False,
    )
    db.commit()
    is_search = job.collector_kind == SEARCH_COLLECTOR_KIND
    return {
        "job": {
            "id": job.id,
            "kind": "meli_amazon_search" if is_search else "meli_amazon_product",
            "url": job.source_url,
            "sourceUrl": job.source_url,
            "targetSiteId": job.target_site_id,
            "collectorKind": job.collector_kind,
            "campaignId": job.campaign_id,
            "campaignKeyword": job.campaign_keyword,
            "maxProducts": 60 if is_search else None,
        }
    }


def _receive_continuous_search_result(
    db: Session,
    job: CollectionJob,
    payload: AmazonExtensionJobResult,
) -> dict[str, object]:
    if payload.source_url.strip() != job.source_url.strip():
        raise HTTPException(status_code=409, detail="collection_job_source_mismatch")
    campaign = db.get(KeywordCollectionCampaign, job.campaign_id) if job.campaign_id else None
    before_status = job.status.value
    now = datetime.now(UTC)
    if payload.status != "collected":
        job.status = (
            CollectionJobStatus.NEEDS_MANUAL_ACTION
            if payload.status == "needs_manual_action"
            else CollectionJobStatus.FAILED
        )
        job.message = payload.message or (
            "Amazon 搜索页需要人工验证。"
            if payload.status == "needs_manual_action"
            else "本机插件未能读取 Amazon 搜索结果。"
        )
        job.completed_at = now
        job.claimed_by = None
        job.claimed_at = None
        if campaign is not None:
            if job.status == CollectionJobStatus.NEEDS_MANUAL_ACTION:
                campaign.status = KeywordCampaignStatus.PAUSED.value
                campaign.message = "Amazon 搜索页需要人工验证，持续采集已暂停。"
            else:
                _advance_continuous_search_cursor(campaign)
                campaign.message = "一次 Amazon 搜索发现失败；已记录并继续下一轮。"
        create_audit_event(
            db,
            actor_type="extension",
            actor_id=payload.worker_id.strip(),
            action="collection_job.extension_finished",
            entity_type="collection_job",
            entity_id=str(job.id),
            before={"status": before_status},
            after={"status": job.status.value, "message": job.message},
            commit=False,
        )
        db.commit()
        return {"ok": True, "job_id": job.id, "status": job.status.value, "created_count": 0}

    normalized_urls: list[str] = []
    seen: set[str] = set()
    for candidate in payload.product_urls:
        normalized = _try_normalize_amazon_url(candidate)
        if normalized is None or normalized in seen:
            continue
        seen.add(normalized)
        normalized_urls.append(normalized)
    existing = _existing_collection_jobs(db, job.target_site_id, set(normalized_urls))
    new_urls = [url for url in normalized_urls if url not in existing]
    created_jobs = [
        CollectionJob(
            source_url=url,
            source_identity=url,
            target_site_id=job.target_site_id,
            campaign_id=job.campaign_id,
            campaign_keyword=job.campaign_keyword,
            collector_kind=EXTENSION_COLLECTOR_KIND,
            message="等待本机插件采集 Amazon 详情页。",
        )
        for url in new_urls
    ]
    db.add_all(created_jobs)
    db.flush()
    for created in created_jobs:
        create_audit_event(
            db,
            actor_type="system",
            actor_id="continuous-search-discovery",
            action="collection_job.created",
            entity_type="collection_job",
            entity_id=str(created.id),
            after={
                "status": CollectionJobStatus.PENDING.value,
                "source_url": created.source_url,
                "target_site_id": created.target_site_id,
                "campaign_id": created.campaign_id,
                "campaign_keyword": created.campaign_keyword,
                "collector_kind": created.collector_kind,
                "reason": "local_extension_search_result",
            },
            commit=False,
        )
    duplicate_count = len(normalized_urls) - len(new_urls)
    job.status = CollectionJobStatus.COMPLETED
    job.message = f"搜索页发现 {len(normalized_urls)} 个商品；新增 {len(new_urls)} 个，去重 {duplicate_count} 个。"
    job.completed_at = now
    job.claimed_by = None
    job.claimed_at = None
    if campaign is not None:
        campaign.discovered_count += len(normalized_urls)
        campaign.queued_count += len(new_urls)
        campaign.duplicate_count += duplicate_count
        _advance_continuous_search_cursor(campaign)
        campaign.message = (
            f"持续采集运行中；最近发现 {len(normalized_urls)} 个候选，新增 {len(new_urls)} 个详情任务。"
        )
    create_audit_event(
        db,
        actor_type="extension",
        actor_id=payload.worker_id.strip(),
        action="collection_job.amazon_search_finished",
        entity_type="collection_job",
        entity_id=str(job.id),
        before={"status": before_status},
        after={
            "status": job.status.value,
            "discovered_count": len(normalized_urls),
            "created_count": len(new_urls),
            "duplicate_count": duplicate_count,
        },
        commit=False,
    )
    db.commit()
    return {
        "ok": True,
        "job_id": job.id,
        "status": job.status.value,
        "created_count": len(new_urls),
        "duplicate_count": duplicate_count,
    }


@router.post("/amazon-extension/jobs/{job_id}/result")
def receive_amazon_extension_job_result(
    job_id: int,
    payload: AmazonExtensionJobResult,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    # All PostgreSQL paths touching an exact-page collection job take the site
    # advisory lock before the row lock. This matches job creation and avoids
    # a row-lock/advisory-lock inversion when the operator clicks collect while
    # the extension is returning a result.
    job_site_id = db.scalar(
        select(CollectionJob.target_site_id).where(CollectionJob.id == job_id)
    )
    if job_site_id is None:
        raise HTTPException(status_code=404, detail="collection_job_not_found")
    if db.get_bind().dialect.name == "postgresql":
        db.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:lock_name))"),
            {"lock_name": f"amazon_collection:{job_site_id}"},
        )
    job = db.scalar(select(CollectionJob).where(CollectionJob.id == job_id).with_for_update())
    if job is None:
        raise HTTPException(status_code=404, detail="collection_job_not_found")
    if job.status in {CollectionJobStatus.COMPLETED, CollectionJobStatus.SKIPPED}:
        return {"ok": True, "job_id": job.id, "status": job.status.value, "draft_id": job.draft_id, "idempotent": True}
    if job.claimed_by and job.claimed_by != payload.worker_id.strip():
        raise HTTPException(status_code=409, detail="collection_job_claimed_by_another_worker")
    if job.collector_kind == SEARCH_COLLECTOR_KIND:
        return _receive_continuous_search_result(db, job, payload)
    source_url = _normalized_amazon_url_or_422(payload.source_url)
    if source_url != _normalized_amazon_url_or_422(job.source_url):
        raise HTTPException(status_code=409, detail="collection_job_source_mismatch")
    before_status = job.status.value
    if payload.status != "collected":
        job.status = (
            CollectionJobStatus.NEEDS_MANUAL_ACTION
            if payload.status == "needs_manual_action"
            else CollectionJobStatus.FAILED
        )
        job.message = payload.message or (
            "Amazon 需要人工验证。" if payload.status == "needs_manual_action" else "浏览器插件采集失败。"
        )
        job.completed_at = datetime.now(UTC)
        job.claimed_by = None
        job.claimed_at = None
        create_audit_event(
            db,
            actor_type="extension",
            actor_id=payload.worker_id.strip(),
            action="collection_job.extension_finished",
            entity_type="collection_job",
            entity_id=str(job.id),
            before={"status": before_status},
            after={"status": job.status.value, "message": job.message},
            commit=False,
        )
        db.commit()
        return {"ok": True, "job_id": job.id, "status": job.status.value, "draft_id": None}
    raw_snapshot = dict(payload.snapshot)
    video_urls = select_product_video_urls(raw_snapshot.pop("video_urls", []))
    if not raw_snapshot.get("measurements") and raw_snapshot.get("technical_details"):
        raw_snapshot["measurements"] = _extract_measurements(
            raw_snapshot["technical_details"], source_url
        )
    try:
        snapshot = AmazonSourceSnapshot.model_validate({**raw_snapshot, "source_url": source_url})
    except ValueError as exc:
        _finish_extension_job_as_failed(db, job, payload.worker_id, f"invalid_extension_snapshot: {exc}")
        raise HTTPException(status_code=422, detail="invalid_extension_snapshot") from exc
    selected_images = select_listing_images(snapshot.images)
    quality = _extension_capture_quality(snapshot, image_count=len(selected_images), video_count=len(video_urls))
    if not snapshot.title.strip() or not selected_images:
        message = "浏览器插件采集信息不完整：" + "、".join(quality["issues"])
        _finish_extension_job_as_failed(db, job, payload.worker_id, message)
        raise HTTPException(status_code=422, detail={"code": "extension_capture_incomplete", **quality})
    source_brand, brand_filter_reason = _automated_discovery_brand(
        snapshot, job.campaign_keyword
    )
    if job.campaign_id is not None and source_brand:
        job.status = CollectionJobStatus.SKIPPED
        job.message = f"自动选品已跳过品牌商品：{source_brand[:120]}"
        job.completed_at = datetime.now(UTC)
        job.claimed_by = None
        job.claimed_at = None
        create_audit_event(
            db,
            actor_type="extension",
            actor_id=payload.worker_id.strip(),
            action="collection_job.automated_brand_filtered",
            entity_type="collection_job",
            entity_id=str(job.id),
            before={"status": before_status},
            after={
                "status": job.status.value,
                "reason": brand_filter_reason,
                "source_brand": source_brand[:120],
                "campaign_id": job.campaign_id,
                "quality": quality,
            },
            commit=False,
        )
        db.commit()
        return {
            "ok": True,
            "job_id": job.id,
            "status": job.status.value,
            "draft_id": None,
            "quality": quality,
            "skip_reason": brand_filter_reason,
        }
    previous_source_product_id = job.source_product_id
    previous_draft_id = job.draft_id
    existing = _exact_page_draft_for_url(
        db,
        source_url,
        job.target_site_id,
        statuses=(SourceProductStatus.PENDING, *EXACT_PAGE_EVIDENCE_STATUSES),
    )
    if existing is not None:
        source, draft = existing
        _, quality = _apply_extension_snapshot_to_source(
            db, source, snapshot, video_urls
        )
    else:
        source = create_source_product(
            db,
            source_url=source_url,
            status=SourceProductStatus.COLLECTED,
            snapshot=snapshot,
            collection_method="browser_extension",
        )
        variant_asin, variant_attributes = selected_source_variant(snapshot, source.asin)
        draft_payload = normalize_amazon_product(snapshot.model_dump(), job.target_site_id)
        draft_payload.video_urls = video_urls
        draft = create_product_draft(
            db,
            draft_payload,
            source_product_id=source.id,
            source_variant_asin=variant_asin,
            source_variant_attributes=variant_attributes,
            commit=False,
        )
    job.source_product_id = source.id
    job.draft_id = draft.id
    job.status = CollectionJobStatus.COMPLETED
    job.message = "本机浏览器插件采集完成。"
    job.completed_at = datetime.now(UTC)
    job.claimed_by = None
    job.claimed_at = None
    create_audit_event(
        db,
        actor_type="extension",
        actor_id=payload.worker_id.strip(),
        action="collection_job.extension_finished",
        entity_type="collection_job",
        entity_id=str(job.id),
        before={
            "status": before_status,
            "source_product_id": previous_source_product_id,
            "draft_id": previous_draft_id,
        },
        after={
            "status": job.status.value,
            "draft_id": draft.id,
            "source_product_id": source.id,
            "quality": quality,
            "reused_exact_page_draft": existing is not None,
            "previous_source_product_id": previous_source_product_id,
            "previous_draft_id": previous_draft_id,
        },
        commit=False,
    )
    db.commit()
    return {"ok": True, "job_id": job.id, "status": job.status.value, "draft_id": draft.id, "quality": quality}


@router.post("/amazon-extension/jobs/{job_id}/retry")
def retry_amazon_extension_job(
    job_id: int,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    job = db.scalar(select(CollectionJob).where(CollectionJob.id == job_id).with_for_update())
    if job is None:
        raise HTTPException(status_code=404, detail="collection_job_not_found")
    if job.status not in {CollectionJobStatus.FAILED, CollectionJobStatus.NEEDS_MANUAL_ACTION}:
        raise HTTPException(status_code=409, detail="collection_job_not_retryable")
    before = job.status.value
    job.status = CollectionJobStatus.PENDING
    job.message = "已手动重新加入本机插件采集队列。"
    job.started_at = None
    job.completed_at = None
    job.next_attempt_at = None
    job.claimed_by = None
    job.claimed_at = None
    create_audit_event(
        db,
        actor_type="operator",
        actor_id="local-ui",
        action="collection_job.retry_requested",
        entity_type="collection_job",
        entity_id=str(job.id),
        before={"status": before},
        after={"status": job.status.value},
        commit=False,
    )
    db.commit()
    return {"ok": True, "job_id": job.id, "status": job.status.value}


@router.get("/source-products/{source_product_id}", response_model=SourceProductRead)
def get_source_product(
    source_product_id: int,
    db: Session = Depends(get_db),
) -> SourceProductRead:
    source = db.get(SourceProduct, source_product_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source product not found.")
    return to_source_product_read(source)


def _exact_page_draft_for_url(
    db: Session,
    source_url: str,
    target_site_id: str,
    *,
    statuses: set[SourceProductStatus] | tuple[SourceProductStatus, ...],
) -> tuple[SourceProduct, ProductDraft] | None:
    """Return the canonical draft already bound to this exact Amazon page.

    A page can arrive through the first-capture endpoint while a variant
    collection placeholder is already waiting for the same ASIN.  Looking only
    through CollectionJob misses drafts created by the other endpoint and used
    to create a second source/draft for one exact product page.
    """
    normalized_url = _normalized_amazon_url_or_422(source_url)
    asin = normalized_url.rsplit("/", 1)[-1].upper()
    candidates = (
        db.query(SourceProduct, ProductDraft)
        .join(ProductDraft, ProductDraft.source_product_id == SourceProduct.id)
        .filter(
            func.upper(SourceProduct.asin) == asin,
            SourceProduct.raw_status.in_(statuses),
            ProductDraft.target_site_id == target_site_id,
            or_(
                func.upper(ProductDraft.source_variant_asin) == asin,
                ProductDraft.source_variant_asin == "",
            ),
        )
        .order_by(
            (ProductDraft.target_category_id != "").desc(),
            ProductDraft.content_version.desc(),
            ProductDraft.id.asc(),
        )
        .with_for_update()
        .all()
    )
    for source, draft in candidates:
        if _try_normalize_amazon_url(source.source_url) == normalized_url:
            return source, draft
    return None


def _apply_extension_snapshot_to_source(
    db: Session,
    source: SourceProduct,
    snapshot: AmazonSourceSnapshot,
    video_urls: list[str],
) -> tuple[list[ProductDraft], dict[str, object]]:
    """Apply one verified extension capture without replacing draft identity."""
    source_url = _normalized_amazon_url_or_422(snapshot.source_url)
    source.source_url = source_url
    source.asin = source_url.rsplit("/", 1)[-1].upper()
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
    source.variants_json = [
        {**variant.model_dump(), "image_urls": select_listing_images(variant.image_urls)}
        for variant in snapshot.variants
    ]
    source.technical_details_json = snapshot.technical_details
    source.measurements_json = snapshot.measurements.model_dump(exclude_none=True)
    drafts = db.query(ProductDraft).filter(ProductDraft.source_product_id == source.id).all()
    configured_draft_ids = {
        row[0]
        for row in db.query(CbtListingConfig.product_draft_id)
        .filter(CbtListingConfig.product_draft_id.in_([draft.id for draft in drafts]))
        .all()
    } if drafts else set()
    for draft in drafts:
        # Overnight/source refreshes must not replace content that the operator
        # has already saved for publication. The fresh Amazon evidence remains
        # available through the bound source product.
        if draft.id in configured_draft_ids:
            continue
        variant = next(
            (
                row
                for row in source.variants_json
                if str(row.get("asin", "")).upper()
                == (draft.source_variant_asin or "").upper()
            ),
            None,
        )
        images = merge_listing_images(
            variant.get("image_urls", []) if variant else [],
            source.image_urls_json or [],
        )
        variant_attributes = (
            dict(variant.get("attributes") or {}) if isinstance(variant, dict) else {}
        )
        update_draft_content(
            db,
            draft.id,
            expected_content_version=draft.content_version,
            title=(source.title[:60].rstrip() + "...")
            if source.title and len(source.title) > 60
            else source.title,
            description=source.description,
            image_urls_json=images,
            video_urls_json=video_urls,
            source_variant_attributes_json=variant_attributes,
        )
    quality = _extension_capture_quality(
        snapshot,
        image_count=len(source.image_urls_json),
        video_count=len(video_urls),
    )
    return drafts, quality


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
    video_urls = select_product_video_urls(raw_snapshot.pop("video_urls", []))
    if not raw_snapshot.get("measurements") and raw_snapshot.get("technical_details"):
        raw_snapshot["measurements"] = _extract_measurements(
            raw_snapshot["technical_details"], source_url
        )
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

    # A variant collection job may have pre-created an exact-page placeholder
    # before the extension's first-capture callback arrives.  Reuse it instead
    # of producing a second source and a second draft for the same ASIN/site.
    db.rollback()
    _lock_collection_site(db, target_site_id)
    pending = _exact_page_draft_for_url(
        db,
        source_url,
        target_site_id,
        statuses=(SourceProductStatus.PENDING,),
    )
    if pending is not None:
        source, draft = pending
        # 【2026-09-16 迭代】draft_id 复用：把绑定采集任务的现有草稿先切到变体 source，
        # 让 _apply_extension_snapshot_to_source 用变体页真实数据刷新它（不新建草稿）
        rebind_jobs = (
            db.query(CollectionJob)
            .filter(
                CollectionJob.target_site_id == target_site_id,
                CollectionJob.source_identity == source_url,
                CollectionJob.status.in_([
                    CollectionJobStatus.PENDING,
                    CollectionJobStatus.RUNNING,
                ]),
            )
            .all()
        )
        for rebind in rebind_jobs:
            if rebind.draft_id is None:
                continue
            cur = db.get(ProductDraft, rebind.draft_id)
            if cur is not None and cur.source_product_id != source.id:
                cur.source_product_id = source.id
        drafts, quality = _apply_extension_snapshot_to_source(
            db, source, snapshot, video_urls
        )
        completed_job_ids: list[int] = []
        related_jobs = (
            db.query(CollectionJob)
            .filter(
                CollectionJob.target_site_id == target_site_id,
                CollectionJob.source_identity == source_url,
                CollectionJob.status.in_([
                    CollectionJobStatus.PENDING,
                    CollectionJobStatus.RUNNING,
                ]),
                or_(
                    CollectionJob.source_product_id == source.id,
                    CollectionJob.draft_id == draft.id,
                ),
            )
            .with_for_update()
            .all()
        )
        for job in related_jobs:
            before_job = {
                "status": job.status.value,
                "source_product_id": job.source_product_id,
                "draft_id": job.draft_id,
            }
            job.source_product_id = source.id
            job.draft_id = draft.id
            job.status = CollectionJobStatus.COMPLETED
            job.message = "首次采集回传已填充变体占位草稿。"
            job.completed_at = datetime.now(UTC)
            job.claimed_by = None
            job.claimed_at = None
            completed_job_ids.append(job.id)
            create_audit_event(
                db,
                actor_type="extension",
                actor_id="browser-extension",
                action="collection_job.extension_finished",
                entity_type="collection_job",
                entity_id=str(job.id),
                before=before_job,
                after={
                    "status": job.status.value,
                    "source_product_id": source.id,
                    "draft_id": draft.id,
                    "quality": quality,
                    "reason": "completed_by_first_capture",
                },
                commit=False,
            )
        create_audit_event(
            db,
            actor_type="extension",
            actor_id="browser-extension",
            action="source_product.extension_capture_reused",
            entity_type="source_product",
            entity_id=str(source.id),
            after={
                "draft_id": draft.id,
                "draft_count": len(drafts),
                "target_site_id": target_site_id,
                "quality": quality,
                "reason": "exact_page_draft_exists",
                "completed_collection_job_ids": completed_job_ids,
            },
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
            "reused": True,
        }

    # `/amazon-extension/capture` is the create-only contract. A repeated
    # callback for an already collected page must be idempotent and must not
    # overwrite title/description/media that the operator may have edited.
    # Intentional updates use `/source-products/{id}/extension-capture`.
    collected = _exact_page_draft_for_url(
        db,
        source_url,
        target_site_id,
        statuses=EXACT_PAGE_EVIDENCE_STATUSES,
    )
    if collected is not None:
        source, draft = collected
        create_audit_event(
            db,
            actor_type="extension",
            actor_id="browser-extension",
            action="source_product.extension_duplicate_ignored",
            entity_type="source_product",
            entity_id=str(source.id),
            after={
                "draft_id": draft.id,
                "target_site_id": target_site_id,
                "quality": quality,
                "reason": "exact_page_already_collected",
            },
            commit=False,
        )
        db.commit()
        return {
            "ok": True,
            "id": draft.id,
            "draft_id": draft.id,
            "source_product_id": source.id,
            "quality": quality,
            "reused": True,
            "idempotent": True,
        }

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
    create_audit_event(
        db,
        actor_type="extension",
        actor_id="browser-extension",
        action="source_product.extension_captured",
        entity_type="source_product",
        entity_id=str(source.id),
        after={"draft_id": draft.id, "target_site_id": target_site_id, "quality": quality},
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
    video_urls = select_product_video_urls(raw_snapshot.pop("video_urls", []))
    if not raw_snapshot.get("measurements") and raw_snapshot.get("technical_details"):
        raw_snapshot["measurements"] = _extract_measurements(
            raw_snapshot["technical_details"], source_url
        )
    try:
        snapshot = AmazonSourceSnapshot.model_validate({**raw_snapshot, "source_url": source_url})
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"invalid_extension_snapshot: {exc}") from exc
    selected_images = select_listing_images(snapshot.images)
    capture_quality = _extension_capture_quality(
        snapshot,
        image_count=len(selected_images),
        video_count=len(video_urls),
    )
    if not snapshot.title.strip() or not selected_images:
        raise HTTPException(
            status_code=422,
            detail={"code": "extension_capture_incomplete", **capture_quality},
        )
    related_jobs = (
        db.query(CollectionJob)
        .filter(
            CollectionJob.source_product_id == source.id,
            CollectionJob.collector_kind == RECOLLECT_COLLECTOR_KIND,
            CollectionJob.status.in_([CollectionJobStatus.PENDING, CollectionJobStatus.RUNNING]),
        )
        .with_for_update()
        .all()
    )
    campaign_job = next((job for job in related_jobs if job.campaign_id is not None), None)
    source_brand, brand_filter_reason = _automated_discovery_brand(
        snapshot,
        campaign_job.campaign_keyword if campaign_job is not None else None,
    )
    if campaign_job is not None and source_brand:
        for job in related_jobs:
            job.status = CollectionJobStatus.SKIPPED
            job.message = f"自动选品已跳过品牌商品：{source_brand[:120]}"
            job.completed_at = datetime.now(UTC)
            job.claimed_by = None
            job.claimed_at = None
            create_audit_event(
                db,
                actor_type="extension",
                actor_id="listing-recollect-driver",
                action="collection_job.automated_brand_filtered",
                entity_type="collection_job",
                entity_id=str(job.id),
                before={"status": CollectionJobStatus.RUNNING.value},
                after={
                    "status": job.status.value,
                    "reason": brand_filter_reason,
                    "source_brand": source_brand[:120],
                    "campaign_id": job.campaign_id,
                    "protocol": "meli-amazon-recollect",
                },
                commit=False,
            )
        has_draft = db.query(ProductDraft.id).filter(ProductDraft.source_product_id == source.id).first() is not None
        if not has_draft and source.raw_status == SourceProductStatus.PENDING:
            for job in related_jobs:
                job.source_product_id = None
            db.delete(source)
        db.commit()
        return {
            "ok": True,
            "source_product_id": source_product_id,
            "draft_count": 0,
            "quality": capture_quality,
            "skipped": True,
        }
    drafts, quality = _apply_extension_snapshot_to_source(
        db, source, snapshot, video_urls
    )
    if not drafts and _source_has_deleted_draft(db, source.id):
        skipped_job_ids: list[int] = []
        for job in related_jobs:
            previous_status = job.status.value
            job.status = CollectionJobStatus.SKIPPED
            job.message = "原草稿已由操作员删除；补采结果仅更新 source，不重建上架库草稿。"
            job.completed_at = datetime.now(UTC)
            job.claimed_by = None
            job.claimed_at = None
            skipped_job_ids.append(job.id)
            create_audit_event(
                db,
                actor_type="extension",
                actor_id="listing-recollect-driver",
                action="collection_job.recreate_blocked_by_draft_delete",
                entity_type="collection_job",
                entity_id=str(job.id),
                before={"status": previous_status},
                after={
                    "status": CollectionJobStatus.SKIPPED.value,
                    "source_product_id": source.id,
                    "protocol": "meli-amazon-recollect",
                },
                commit=False,
            )
        create_audit_event(
            db,
            actor_type="extension",
            actor_id="browser-extension",
            action="source_product.recollect_draft_recreation_blocked",
            entity_type="source_product",
            entity_id=str(source.id),
            after={
                "draft_count": 0,
                "quality": quality,
                "skipped_collection_job_ids": skipped_job_ids,
            },
            commit=False,
        )
        db.commit()
        return {
            "ok": True,
            "source_product_id": source.id,
            "draft_count": 0,
            "quality": quality,
            "completed_collection_job_ids": [],
            "skipped": True,
            "reason": "draft_deleted",
        }
    if not drafts:
        target_site_id = related_jobs[0].target_site_id if related_jobs else "CBT"
        draft_payload = normalize_amazon_product(snapshot.model_dump(), target_site_id)
        draft_payload.video_urls = video_urls
        variant_asin, variant_attributes = selected_source_variant(snapshot, source.asin)
        draft = create_product_draft(
            db,
            draft_payload,
            source_product_id=source.id,
            source_variant_asin=variant_asin,
            source_variant_attributes=variant_attributes,
            commit=False,
        )
        drafts = [draft]
    completed_job_ids: list[int] = []
    for job in related_jobs:
        job.status = CollectionJobStatus.COMPLETED
        job.message = "已通过上架库绿色“采”流程完成补采。"
        job.draft_id = drafts[0].id
        job.completed_at = datetime.now(UTC)
        job.claimed_by = None
        job.claimed_at = None
        completed_job_ids.append(job.id)
        create_audit_event(
            db,
            actor_type="extension",
            actor_id="listing-recollect-driver",
            action="collection_job.listing_recollect_finished",
            entity_type="collection_job",
            entity_id=str(job.id),
            before={"status": CollectionJobStatus.RUNNING.value},
            after={
                "status": job.status.value,
                "source_product_id": source.id,
                "draft_id": drafts[0].id,
                "quality": quality,
                "protocol": "meli-amazon-recollect",
            },
            commit=False,
        )
    create_audit_event(
        db,
        actor_type="extension",
        actor_id="browser-extension",
        action="source_product.extension_recollected",
        entity_type="source_product",
        entity_id=str(source.id),
        after={
            "draft_count": len(drafts),
            "quality": quality,
            "variant_attributes_updated": sum(
                1
                for draft in drafts
                if any(
                    str(row.get("asin", "")).upper()
                    == (draft.source_variant_asin or "").upper()
                    for row in source.variants_json
                    if isinstance(row, dict)
                )
            ),
            "completed_collection_job_ids": completed_job_ids,
        },
        commit=False,
    )
    db.commit()
    return {
        "ok": True,
        "source_product_id": source.id,
        "draft_count": len(drafts),
        "quality": quality,
        "completed_collection_job_ids": completed_job_ids,
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
        if exact_draft is not None:
            return to_draft_read(exact_draft)
        # 该变体还没有单独采集页面：直接用 parent 快照里的变体数据创建独立草稿。
        try:
            draft, _ = create_or_get_source_variant_draft(
                db, source, normalized_asin, target_site_id
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        create_audit_event(
            db,
            actor_type="operator",
            actor_id="web",
            action="source_product.variant_draft_opened",
            entity_type="product_draft",
            entity_id=str(draft.id),
            after={
                "source_product_id": source_product_id,
                "source_variant_asin": normalized_asin,
                "target_site_id": target_site_id,
            },
            commit=True,
        )
        return to_draft_read(draft)
    try:
        draft, _ = create_or_get_source_variant_draft(
            db, source, normalized_asin, target_site_id
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    create_audit_event(
        db,
        actor_type="operator",
        actor_id="web",
        action="source_product.variant_draft_opened",
        entity_type="product_draft",
        entity_id=str(draft.id),
        after={
            "source_product_id": source_product_id,
            "source_variant_asin": normalized_asin,
            "target_site_id": target_site_id,
        },
        commit=True,
    )
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
    exact = _exact_page_draft_for_url(
        db,
        variant_url,
        target_site_id,
        statuses=EXACT_PAGE_EVIDENCE_STATUSES,
    )
    return exact[1] if exact is not None else None


def _prepare_variant_extension_placeholders(
    db: Session,
    parent_source: SourceProduct,
    normalized_asin: str,
    variant_url: str,
    target_site_id: str,
) -> tuple[SourceProduct, ProductDraft]:
    """为浏览器插件采集变体页预建占位 source 和草稿。

    插件回报（extension-capture）会按 source 更新真实数据，因此草稿必须绑定
    变体页自己的 source 才能被更新；若草稿尚未建立，先用父快照的该变体数据
    预建，保证插件未响应时用户也能立刻打开可编辑草稿。
    """
    exact = _exact_page_draft_for_url(
        db,
        variant_url,
        target_site_id,
        statuses=(SourceProductStatus.PENDING, *EXACT_PAGE_EVIDENCE_STATUSES),
    )
    if exact is not None:
        return exact
    placeholder = SourceProduct(
        source_url=variant_url,
        asin=normalized_asin,
        raw_status=SourceProductStatus.PENDING,
        collection_method="browser_extension",
        source="amazon",
    )
    db.add(placeholder)
    db.flush()
    source_read = to_source_product_read(parent_source)
    snapshot = source_read.snapshot
    if snapshot is None:
        raise HTTPException(status_code=409, detail="source_snapshot_unavailable")
    variant = next(
        (item for item in snapshot.variants if item.asin == normalized_asin),
        None,
    )
    if variant is None and str(getattr(snapshot, "asin", "")).upper() == normalized_asin:
        # 【2026-09-16 迭代】源本身就是变体页（variants_json 为空）：用变体页自身快照
        # 作为该变体的数据，占位草稿即变体页真实数据，插件回报后再按变体页更新。
        variant = SimpleNamespace(
            asin=normalized_asin,
            attributes=getattr(snapshot, "attributes", None) or {},
            image_urls=getattr(snapshot, "images", None) or [],
        )
    if variant is None:
        raise HTTPException(status_code=404, detail="source_variant_not_found")
    draft_snapshot = snapshot.model_dump()
    draft_snapshot["images"] = merge_listing_images(variant.image_urls, snapshot.images)
    draft_payload = normalize_amazon_product(draft_snapshot, target_site_id)
    # 占位草稿先用父页标题，截断到界面/序列化允许的 60 字符；插件回报后会被变体页真实标题覆盖
    if draft_payload.title and len(draft_payload.title) > 60:
        draft_payload.title = draft_payload.title[:60].rstrip() + "..."
    if variant.attributes:
        variant_lines = "\n".join(
            f"{name}: {value}" for name, value in variant.attributes.items()
        )
        draft_payload.description = "\n\n".join(
            part
            for part in [draft_payload.description, f"Amazon variant:\n{variant_lines}"]
            if part
        )
    draft = create_product_draft(
        db,
        draft_payload,
        source_product_id=placeholder.id,
        source_variant_asin=normalized_asin,
        source_variant_attributes=variant.attributes,
        commit=False,
    )
    return placeholder, draft


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
    # 【2026-09-16 迭代】放宽变体验证：ASIN 格式合法即可创建采集任务。
    # 变体草稿的 source_variant_asin 由系统记录（可信），且部分源本身就是变体页
    # （variants_json 为空），此前要求 ASIN 必须在父源 variants_json 中导致
    # “源资源丢失”死胡同（AI 生成要源数据 → 提示点采 → 采报错）。
    if not re.fullmatch(r"[A-Z0-9]{10}", normalized_asin):
        raise HTTPException(status_code=404, detail="source_variant_not_found")
    target_site_id = _target_site_or_422(payload.target_site_id)
    normalized_source_url = _normalized_amazon_url_or_422(source.source_url)
    source_parts = urlparse(normalized_source_url)
    variant_url = f"{source_parts.scheme}://{source_parts.netloc}/dp/{normalized_asin}"
    db.rollback()
    _lock_collection_site(db, target_site_id)
    existing = _existing_collection_jobs(db, target_site_id, {variant_url}).get(variant_url)
    if existing is not None:
        if existing.status == CollectionJobStatus.FAILED:
            # 上次变体页采集失败：重置为 pending 重新入队，让本次“编辑此变体”能再试一次拿到真实数据
            existing.status = CollectionJobStatus.PENDING
            existing.started_at = None
            existing.completed_at = None
            existing.next_attempt_at = None
            existing.message = ""
            db.commit()
            db.refresh(existing)
        if (
            payload.collector_kind == "browser_extension"
            and (existing.source_product_id is None or existing.draft_id is None)
        ):
            placeholder, draft = _prepare_variant_extension_placeholders(
                db, source, normalized_asin, variant_url, target_site_id
            )
            existing.source_product_id = placeholder.id
            existing.draft_id = draft.id
            existing.collector_kind = "browser_extension"
            db.commit()
            db.refresh(existing)
        if payload.draft_id is not None and existing.draft_id != payload.draft_id:
            # 【2026-09-16 迭代】复用当前草稿：把任务绑定切到现有草稿，避免“采”后新建草稿
            stale = db.get(ProductDraft, existing.draft_id) if existing.draft_id else None
            existing.draft_id = payload.draft_id
            existing.collector_kind = "browser_extension"
            # 只删“其他占位草稿”，绝不删正在刷新的当前草稿
            if (
                stale is not None
                and stale.id != payload.draft_id
                and stale.source_product_id == existing.source_product_id
            ):
                db.delete(stale)
            db.commit()
            db.refresh(existing)
        existing_source = (
            db.get(SourceProduct, existing.source_product_id)
            if existing.source_product_id is not None
            else None
        )
        return to_collection_job_read(existing, existing_source)
    if payload.collector_kind == "browser_extension":
        placeholder, draft = _prepare_variant_extension_placeholders(
            db, source, normalized_asin, variant_url, target_site_id
        )
        if payload.draft_id is not None:
            # 【2026-09-16 迭代】复用当前草稿：占位草稿删除，回报后当前草稿切到变体 source 并刷新
            current = db.get(ProductDraft, payload.draft_id)
            if current is None:
                raise HTTPException(status_code=404, detail="Product draft not found.")
            # 占位草稿可能恰好就是当前草稿（变体页已采集过、exact 命中时），此时不删
            if draft.id != current.id:
                db.delete(draft)
                db.flush()
            job = create_collection_job(db, variant_url, target_site_id, collector_kind="browser_extension")
            job.source_product_id = placeholder.id
            job.draft_id = current.id
            db.commit()
            db.refresh(job)
            return to_collection_job_read(job)
        job = create_collection_job(db, variant_url, target_site_id, collector_kind="browser_extension")
        job.source_product_id = placeholder.id
        job.draft_id = draft.id
        db.commit()
        db.refresh(job)
        return to_collection_job_read(job)
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
    requested_asins = [asin.strip().upper() for asin in (payload.variant_asins or [])]
    if requested_asins:
        requested_set = set(requested_asins)
        variant_asins = [
            asin
            for asin, selected in selected_by_asin.items()
            if not selected and asin in requested_set
        ]
    else:
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


def _finish_extension_job_as_failed(
    db: Session, job: CollectionJob, worker_id: str, message: str
) -> None:
    before = job.status.value
    job.status = CollectionJobStatus.FAILED
    job.message = message[:2000]
    job.completed_at = datetime.now(UTC)
    job.claimed_by = None
    job.claimed_at = None
    create_audit_event(
        db,
        actor_type="extension",
        actor_id=worker_id.strip(),
        action="collection_job.extension_finished",
        entity_type="collection_job",
        entity_id=str(job.id),
        before={"status": before},
        after={"status": job.status.value, "message": job.message},
        commit=False,
    )
    db.commit()


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

