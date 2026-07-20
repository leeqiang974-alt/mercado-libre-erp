from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.config import get_settings
from app.schemas.drafts import PersistedDraftResponse, ProductDraftCreate
from app.services.amazon.collector import (
    CollectionResult,
    collect_amazon_page,
    validate_amazon_snapshot,
)
from app.services.amazon.normalizer import normalize_amazon_product
from app.services.drafts import create_product_draft
from app.services.source_products import create_source_product
from app.models.source_product import SourceProductStatus
from app.services.collection_jobs import (
    create_collection_job,
    list_collection_jobs,
    run_collection_job,
    to_collection_job_read,
)
from app.schemas.collection_jobs import CollectionJobRead

router = APIRouter(prefix="/api/imports", tags=["imports"])
settings = get_settings()


class AmazonHtmlImport(BaseModel):
    source_url: str
    html: str
    target_site_id: str = "MLM"
    persist: bool = False


class AmazonUrlImport(BaseModel):
    source_url: str
    target_site_id: str = "MLM"
    persist: bool = False


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
    )
    model = create_product_draft(db, draft, source_product_id=source.id)
    return PersistedDraftResponse(id=model.id, draft=draft)


@router.post("/amazon-url", response_model=CollectionResult)
async def import_amazon_url(
    payload: AmazonUrlImport, db: Session = Depends(get_db)
) -> CollectionResult:
    result = await collect_amazon_page(payload.source_url, payload.target_site_id)
    if not payload.persist:
        return result
    status_map = {
        "collected": SourceProductStatus.COLLECTED,
        "needs_manual_action": SourceProductStatus.NEEDS_MANUAL_ACTION,
        "failed": SourceProductStatus.FAILED,
    }
    source = create_source_product(
        db,
        source_url=payload.source_url,
        status=status_map[result.status.value],
        collection_error="" if result.status.value == "collected" else result.message,
    )
    draft_model = None
    if result.draft:
        draft_model = create_product_draft(db, result.draft, source_product_id=source.id)
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
    job = create_collection_job(
        db=db,
        source_url=payload.source_url,
        target_site_id=payload.target_site_id,
    )
    return to_collection_job_read(job)


@router.get("/amazon-url/jobs", response_model=list[CollectionJobRead])
def get_amazon_url_collection_jobs(db: Session = Depends(get_db)) -> list[CollectionJobRead]:
    return list_collection_jobs(db)


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
    return to_collection_job_read(job)
