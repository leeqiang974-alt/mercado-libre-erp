from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.drafts import PersistedDraftResponse, ProductDraftCreate
from app.services.amazon.collector import CollectionResult, collect_amazon_page
from app.services.amazon.normalizer import normalize_amazon_product
from app.services.amazon.parser import parse_amazon_html
from app.services.drafts import create_product_draft
from app.services.source_products import create_source_product
from app.models.source_product import SourceProductStatus

router = APIRouter(prefix="/api/imports", tags=["imports"])


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
    parsed = parse_amazon_html(payload.html, payload.source_url)
    draft = normalize_amazon_product(parsed, payload.target_site_id)
    if not payload.persist:
        return draft
    model = create_product_draft(db, draft)
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
