from pydantic import BaseModel, Field


class ListingChoice(BaseModel):
    site_id: str
    listing_type_id: str
    fulfillment: str = "not_full"
    attributes: list[dict] = Field(default_factory=list)


class PublishValidationResult(BaseModel):
    allowed: bool
    errors: list[str] = Field(default_factory=list)


class PublishExecutionResult(BaseModel):
    status: str
    item_id: str = ""
    permalink: str = ""
    shipping_mode: str = ""
    errors: list[str] = Field(default_factory=list)
    job_id: int | None = None


class PublishJobRead(BaseModel):
    id: int
    product_draft_id: int
    store_id: int
    status: str
    item_id: str = ""
    permalink: str = ""
    shipping_mode: str = ""
    errors: list[str] = Field(default_factory=list)
