from typing import Literal
from datetime import datetime

from pydantic import BaseModel, Field


class ListingChoice(BaseModel):
    site_id: str
    store_id: int | None = None
    listing_type_id: str
    fulfillment: str = "not_full"
    shipping_mode: str = ""
    shipping_logistic_type: str = ""
    attributes: list[dict] = Field(default_factory=list)


class PublishValidationResult(BaseModel):
    allowed: bool
    errors: list[str] = Field(default_factory=list)


class PublishExecutionResult(BaseModel):
    status: str
    item_id: str = ""
    permalink: str = ""
    shipping_mode: str = ""
    shipping_logistic_type: str = ""
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
    shipping_logistic_type: str = ""
    errors: list[str] = Field(default_factory=list)
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


class PublishBatchEnqueueRequest(BaseModel):
    draft_ids: list[int] = Field(min_length=1, max_length=50)
    acknowledge_publish: bool = False


class PublishBatchPreflightRequest(BaseModel):
    draft_ids: list[int] = Field(min_length=1, max_length=50)


class PublishBatchPreflightItem(BaseModel):
    draft_id: int
    outcome: Literal["ready", "not_ready", "not_found"]
    errors: list[str] = Field(default_factory=list)


class PublishBatchPreflightResult(BaseModel):
    ready_count: int
    not_ready_count: int
    not_found_count: int
    items: list[PublishBatchPreflightItem]


class PublishBatchItem(BaseModel):
    draft_id: int
    outcome: Literal["queued", "existing", "not_ready", "not_found"]
    errors: list[str] = Field(default_factory=list)
    job: PublishJobRead | None = None


class PublishBatchEnqueueResult(BaseModel):
    batch_id: str
    queued_count: int
    existing_count: int
    not_ready_count: int
    not_found_count: int
    items: list[PublishBatchItem]
