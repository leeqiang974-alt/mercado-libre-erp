from datetime import datetime

from pydantic import BaseModel, Field


class SourcePrice(BaseModel):
    amount: float | None = None
    currency: str = ""


class AmazonSourceVariant(BaseModel):
    asin: str
    attributes: dict[str, str] = Field(default_factory=dict)
    image_urls: list[str] = Field(default_factory=list)
    selected: bool = False


class SourceWeight(BaseModel):
    value: float
    unit: str
    raw: str
    source_label: str


class SourceDimensions(BaseModel):
    length: float
    width: float
    height: float
    unit: str
    raw: str
    source_label: str


class AmazonSourceMeasurements(BaseModel):
    item_weight: SourceWeight | None = None
    package_weight: SourceWeight | None = None
    product_dimensions: SourceDimensions | None = None
    package_dimensions: SourceDimensions | None = None


class AmazonSourceSnapshot(BaseModel):
    source_url: str
    title: str = ""
    price: SourcePrice = Field(default_factory=SourcePrice)
    brand: str = ""
    bullets: list[str] = Field(default_factory=list)
    description: str = ""
    images: list[str] = Field(default_factory=list)
    variants: list[AmazonSourceVariant] = Field(default_factory=list)
    technical_details: dict[str, str] = Field(default_factory=dict)
    measurements: AmazonSourceMeasurements = Field(default_factory=AmazonSourceMeasurements)


class SourceProductRead(BaseModel):
    id: int
    source: str
    source_url: str
    asin: str
    status: str
    collection_method: str
    collected_at: datetime | None = None
    collection_error: str = ""
    snapshot: AmazonSourceSnapshot | None = None


class SourceProductSummaryRead(BaseModel):
    id: int
    asin: str
    status: str
    collection_method: str
    title: str = ""
    brand: str = ""
    source_price: float | None = None
    source_currency: str = ""
    primary_image_url: str = ""
    image_count: int = 0
    variant_count: int = 0
    has_snapshot: bool = False
    collection_error: str = ""


class SourceVariantDraftCreate(BaseModel):
    target_site_id: str = "MLM"


class SourceVariantCollectionCreate(BaseModel):
    target_site_id: str = "MLM"
