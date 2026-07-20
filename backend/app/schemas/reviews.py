from datetime import datetime

from pydantic import BaseModel, Field


class ReviewResponse(BaseModel):
    provider: str
    decision: str
    risk_level: str
    reason_codes: list[str]
    reasons: list[str]
    suggested_changes: dict = Field(default_factory=dict)
    review_result_id: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    provider_request_id: str = ""


class ReviewResultRead(BaseModel):
    id: int
    product_draft_id: int
    provider: str
    model: str = ""
    prompt_version: str = ""
    duration_ms: int = 0
    provider_status: str = "completed"
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    provider_request_id: str = ""
    decision: str
    risk_level: str
    reason_codes: list[str]
    reasons: list[str]
    suggested_changes: dict = Field(default_factory=dict)
    created_at: datetime


class BehavioralAuditResponse(BaseModel):
    nvidia: ReviewResponse
    claude: ReviewResponse
    aggregate: ReviewResponse
