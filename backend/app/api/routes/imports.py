from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.drafts import PersistedDraftResponse, ProductDraftCreate
from app.services.amazon.collector import CollectionResult, collect_amazon_page
from app.services.amazon.normalizer import normalize_amazon_product
from app.services.amazon.parser import parse_amazon_html
from app.services.drafts import create_product_draft

router = APIRouter(prefix="/api/imports", tags=["imports"])


class AmazonHtmlImport(BaseModel):
    source_url: str
    html: str
    target_site_id: str = "MLM"
    persist: bool = False


class AmazonUrlImport(BaseModel):
    source_url: str
    target_site_id: str = "MLM"


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
async def import_amazon_url(payload: AmazonUrlImport) -> CollectionResult:
    return await collect_amazon_page(payload.source_url, payload.target_site_id)
