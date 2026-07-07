from datetime import datetime

from pydantic import BaseModel


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
