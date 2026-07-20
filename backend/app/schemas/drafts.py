from pydantic import BaseModel, Field


class ProductDraftCreate(BaseModel):
    title: str = Field(default="", max_length=200)
    description: str = ""
    brand: str = ""
    target_site_id: str = "MLM"
    target_category_id: str = ""
    condition: str = ""
    source_price: float | None = None
    source_currency: str = ""
    price: float | None = None
    currency: str = ""
    stock: int = 0
    listing_type_id: str = ""
    image_urls: list[str] = Field(default_factory=list)
    attributes: list[dict] = Field(default_factory=list)


class ProductDraftRead(ProductDraftCreate):
    id: int
    source_product_id: int | None = None
    source_variant_asin: str = ""
    source_variant_attributes: dict[str, str] = Field(default_factory=dict)
    status: str
    risk_status: str


class PersistedDraftResponse(BaseModel):
    id: int | None = None
    draft: ProductDraftCreate
