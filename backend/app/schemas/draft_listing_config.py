from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class ListingAttributeValue(BaseModel):
    id: str
    value_name: str


class DraftListingConfigUpsert(BaseModel):
    site_id: str
    category_id: str
    listing_type_id: str
    fulfillment: str = "not_full"
    attributes: list[ListingAttributeValue] = Field(default_factory=list)

    @field_validator("fulfillment")
    @classmethod
    def reject_full_fulfillment(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized == "full":
            raise ValueError("FULL fulfillment is excluded from this system.")
        return normalized


class DraftListingConfigRead(DraftListingConfigUpsert):
    id: int
    product_draft_id: int
    created_at: datetime
    updated_at: datetime
