from pydantic import BaseModel


class ReviewResponse(BaseModel):
    provider: str
    decision: str
    risk_level: str
    reason_codes: list[str]
    reasons: list[str]
    suggested_changes: dict = {}
    review_result_id: int | None = None


class ReviewResultRead(BaseModel):
    id: int
    product_draft_id: int
    provider: str
    model: str = ""
    decision: str
    risk_level: str
    reason_codes: list[str]
    reasons: list[str]
    suggested_changes: dict = {}
