from pydantic import BaseModel


class ListingChoice(BaseModel):
    site_id: str
    listing_type_id: str
    fulfillment: str = "not_full"


class PublishValidationResult(BaseModel):
    allowed: bool
    errors: list[str]
