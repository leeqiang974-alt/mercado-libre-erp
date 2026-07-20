from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator


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
    content_version: int


class ProductDraftContentUpdate(BaseModel):
    expected_content_version: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=50000)
    brand: str = Field(default="", max_length=120)
    image_urls: list[str] = Field(default_factory=list, max_length=12)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("title must not be blank")
        return normalized

    @field_validator("brand")
    @classmethod
    def strip_brand(cls, value: str) -> str:
        return " ".join(value.split())

    @field_validator("description")
    @classmethod
    def strip_description(cls, value: str) -> str:
        return value.strip()

    @field_validator("image_urls")
    @classmethod
    def validate_image_urls(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for value in values:
            candidate = value.strip()
            parsed = urlsplit(candidate)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError("image URLs must be absolute HTTP(S) URLs")
            if candidate not in seen:
                normalized.append(candidate)
                seen.add(candidate)
        return normalized


class PersistedDraftResponse(BaseModel):
    id: int | None = None
    draft: ProductDraftCreate
