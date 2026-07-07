from pydantic import BaseModel


class ListingChoice(BaseModel):
    site_id: str
    listing_type_id: str
    fulfillment: str = "not_full"
    attributes: list[dict] = []


class PublishValidationResult(BaseModel):
    allowed: bool
    errors: list[str]


class PublishExecutionResult(BaseModel):
    status: str
    item_id: str = ""
    permalink: str = ""
    errors: list[str] = []
    job_id: int | None = None


class PublishJobRead(BaseModel):
    id: int
    product_draft_id: int
    store_id: int
    status: str
    item_id: str = ""
    permalink: str = ""
    errors: list[str] = []
