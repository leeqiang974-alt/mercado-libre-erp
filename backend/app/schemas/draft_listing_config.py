from datetime import datetime

from pydantic import BaseModel, field_validator


class ListingAttributeValue(BaseModel):
    id: str
    value_name: str


class DraftListingConfigUpsert(BaseModel):
    site_id: str
    category_id: str
    listing_type_id: str
    fulfillment: str = "not_full"
    attributes: list[ListingAttributeValue] = []

    @field_validator("fulfillment")
    @classmethod
    def reject_full_fulfillment(cls, value: str) -> str:
        if value.lower() == "full":
            raise ValueError("FULL fulfillment is excluded from this system.")
        return value


class DraftListingConfigRead(DraftListingConfigUpsert):
    id: int
    product_draft_id: int
    created_at: datetime
    updated_at: datetime
