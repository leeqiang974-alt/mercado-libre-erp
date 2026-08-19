from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator


UNBRANDED = "Unbranded"
MARKETING_TERMS = (
    "best", "top", "hot", "sale", "discount", "free shipping", "limited",
    "premium", "buy now", "deal", "clearance", "guaranteed",
)


class ProductDraftCreate(BaseModel):
    title: str = Field(default="", max_length=60)
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
    video_urls: list[str] = Field(default_factory=list)
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
    title: str = Field(min_length=1, max_length=60)
    description: str = Field(default="", max_length=50000)
    brand: str = Field(default=UNBRANDED, max_length=120)
    image_urls: list[str] = Field(default_factory=list, max_length=12)
    video_urls: list[str] = Field(default_factory=list, max_length=3)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("title must not be blank")
        if len(normalized) > 60:
            raise ValueError("title must be 60 characters or fewer")
        if any(ord(char) > 127 for char in normalized):
            raise ValueError("title must be in English")
        lowered = normalized.lower()
        if any(term in lowered for term in MARKETING_TERMS):
            raise ValueError("title contains a prohibited marketing term")
        return normalized

    @field_validator("brand")
    @classmethod
    def strip_brand(cls, value: str) -> str:
        return UNBRANDED

    @field_validator("description")
    @classmethod
    def strip_description(cls, value: str) -> str:
        return value.strip()

    @field_validator("image_urls")
    @classmethod
    def validate_image_urls(cls, values: list[str]) -> list[str]:
        return _validate_media_urls(values, "image")

    @field_validator("video_urls")
    @classmethod
    def validate_video_urls(cls, values: list[str]) -> list[str]:
        return _validate_media_urls(values, "video")


def _validate_media_urls(values: list[str], media_type: str) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        candidate = value.strip()
        parsed = urlsplit(candidate)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError(f"{media_type} URLs must be absolute HTTP(S) URLs")
        if candidate not in seen:
            normalized.append(candidate)
            seen.add(candidate)
    return normalized


class PersistedDraftResponse(BaseModel):
    id: int | None = None
    draft: ProductDraftCreate
