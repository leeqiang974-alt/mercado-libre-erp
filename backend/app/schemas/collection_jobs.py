from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.source_products import SourceProductSummaryRead


class CollectionJobRead(BaseModel):
    id: int
    source_url: str
    target_site_id: str
    status: str
    message: str
    source_product_id: int | None = None
    draft_id: int | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    source_product: SourceProductSummaryRead | None = None


class CollectionBatchItemRead(BaseModel):
    input_url: str
    normalized_url: str = ""
    outcome: Literal["created", "duplicate_input", "existing", "invalid"]
    detail: str = ""
    job: CollectionJobRead | None = None


class CollectionBatchRead(BaseModel):
    created_count: int
    duplicate_count: int
    existing_count: int
    invalid_count: int
    items: list[CollectionBatchItemRead]
