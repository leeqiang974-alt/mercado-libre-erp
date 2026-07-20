from typing import Annotated
import re
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, text
from sqlalchemy.orm import Session

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
from app.services.drafts import create_product_draft, to_draft_read
from app.services.source_products import (
    create_or_get_source_variant_draft,
    create_source_product,
    selected_source_variant,
    to_source_product_read,
)
from app.models.source_product import SourceProduct, SourceProductStatus
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
from app.models.collection_job import CollectionJob
from app.services.meli.sites import SITE_CURRENCIES
from app.schemas.source_products import (
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


class AmazonUrlImport(BaseModel):
    source_url: AmazonProductUrl
    target_site_id: str = "MLM"
    persist: bool = False


class AmazonUrlBatchImport(BaseModel):
    source_urls: list[AmazonProductUrl] = Field(min_length=1, max_length=100)
    target_site_id: str = "MLM"
    allow_existing: bool = False


@router.post("/amazon-html")
def import_amazon_html(
    payload: AmazonHtmlImport, db: Session = Depends(get_db)
) -> ProductDraftCreate | PersistedDraftResponse:
    try:
        parsed = validate_amazon_snapshot(payload.source_url, payload.html)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    draft = normalize_amazon_product(parsed, payload.target_site_id)
    if not payload.persist:
        return draft
    source = create_source_product(
        db,
        source_url=payload.source_url,
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
    )
    return PersistedDraftResponse(id=model.id, draft=draft)


@router.post("/amazon-url", response_model=CollectionResult)
async def import_amazon_url(
    payload: AmazonUrlImport, db: Session = Depends(get_db)
) -> CollectionResult:
    source_url = _normalized_amazon_url_or_422(payload.source_url)
    target_site_id = _target_site_or_422(payload.target_site_id)
    result = await collect_amazon_page(source_url, target_site_id)
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
        collection_method="browser_page",
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
    db: Session = Depends(get_db),
) -> list[CollectionJobRead]:
    return list_collection_jobs(db, limit=limit, offset=offset)


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
    try:
        draft, _ = create_or_get_source_variant_draft(
            db, source, variant_asin, target_site_id
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return to_draft_read(draft)


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
