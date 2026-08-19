from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.draft_listing_config import ListingAttributeValue, SUPPORTED_LISTING_TYPE_IDS
from app.schemas.drafts import ProductDraftRead


class CbtSaleTerm(BaseModel):
    id: str = Field(min_length=1, max_length=80)
    value_name: str = Field(min_length=1, max_length=500)

    @field_validator("id")
    @classmethod
    def normalize_id(cls, value: str) -> str:
        return value.strip().upper()


class CbtMarketplaceOffer(BaseModel):
    site_id: str = Field(min_length=3, max_length=8)
    title: str = Field(min_length=3, max_length=60)
    listing_type_id: str
    logistic_type: str = "remote"
    picture_urls: list[str] = Field(default_factory=list, max_length=12)

    @field_validator("site_id")
    @classmethod
    def normalize_site(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("listing_type_id")
    @classmethod
    def listing_type(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in SUPPORTED_LISTING_TYPE_IDS:
            raise ValueError("Only Classic or Premium listing types are supported.")
        return normalized

    @field_validator("logistic_type")
    @classmethod
    def remote_only(cls, value: str) -> str:
        if value.strip().lower() != "remote":
            raise ValueError("Only Remote logistics are supported for CBT listings.")
        return "remote"


class CbtListingConfigUpsert(BaseModel):
    store_id: int
    category_id: str = Field(min_length=4, max_length=40)
    family_name: str = Field(min_length=3, max_length=200)
    global_title: str = Field(min_length=3, max_length=60)
    description: str = Field(min_length=1, max_length=50000)
    price_usd: float = Field(gt=0)
    available_quantity: int = Field(ge=1)
    attributes: list[ListingAttributeValue] = Field(default_factory=list)
    sale_terms: list[CbtSaleTerm] = Field(default_factory=list)
    sites_to_sell: list[CbtMarketplaceOffer] = Field(min_length=1, max_length=6)

    @field_validator("category_id")
    @classmethod
    def cbt_category(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized.startswith("CBT"):
            raise ValueError("Global Selling category ID must start with CBT.")
        return normalized

    @field_validator("family_name", "global_title")
    @classmethod
    def compact_text(cls, value: str) -> str:
        return " ".join(value.split())

    @field_validator("description")
    @classmethod
    def nonempty_description(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def validate_markets_and_attributes(self):
        sites = [offer.site_id for offer in self.sites_to_sell]
        if len(sites) != len(set(sites)):
            raise ValueError("Each target marketplace can only be selected once.")
        attribute_ids = [attribute.id for attribute in self.attributes]
        if len(attribute_ids) != len(set(attribute_ids)):
            raise ValueError("Listing attribute IDs must be unique.")
        return self


class CbtListingConfigRead(BaseModel):
    id: int
    product_draft_id: int
    store_id: int
    category_id: str
    family_name: str
    global_title: str
    description: str
    price_usd: float
    available_quantity: int
    attributes: list[ListingAttributeValue]
    sale_terms: list[CbtSaleTerm]
    sites_to_sell: list[CbtMarketplaceOffer]
    draft_content_version: int
    draft: ProductDraftRead
    created_at: datetime
    updated_at: datetime
