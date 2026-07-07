from datetime import datetime

from pydantic import BaseModel


class DraftApprovalCreate(BaseModel):
    approved_by: str = "operator"
    note: str = ""


class DraftApprovalRead(BaseModel):
    id: int
    product_draft_id: int
    status: str
    approved_by: str
    note: str = ""
    approved_at: datetime
