from fastapi import APIRouter
from pydantic import BaseModel

from app.schemas.drafts import ProductDraftCreate
from app.services.amazon.collector import CollectionResult, collect_amazon_page
from app.services.amazon.normalizer import normalize_amazon_product
from app.services.amazon.parser import parse_amazon_html

router = APIRouter(prefix="/api/imports", tags=["imports"])


class AmazonHtmlImport(BaseModel):
    source_url: str
    html: str
    target_site_id: str = "MLM"


class AmazonUrlImport(BaseModel):
    source_url: str
    target_site_id: str = "MLM"


@router.post("/amazon-html", response_model=ProductDraftCreate)
def import_amazon_html(payload: AmazonHtmlImport) -> ProductDraftCreate:
    parsed = parse_amazon_html(payload.html, payload.source_url)
    return normalize_amazon_product(parsed, payload.target_site_id)


@router.post("/amazon-url", response_model=CollectionResult)
async def import_amazon_url(payload: AmazonUrlImport) -> CollectionResult:
    return await collect_amazon_page(payload.source_url, payload.target_site_id)
