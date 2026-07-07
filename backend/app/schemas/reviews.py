from pydantic import BaseModel


class ReviewResponse(BaseModel):
    provider: str
    decision: str
    risk_level: str
    reason_codes: list[str]
    reasons: list[str]
    suggested_changes: dict = {}
