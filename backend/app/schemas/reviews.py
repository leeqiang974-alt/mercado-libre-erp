from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ReviewResponse(BaseModel):
    provider: str
    decision: Literal["pass", "needs_human_review", "block"]
    risk_level: Literal["low", "medium", "high"]
    reason_codes: list[str]
    reasons: list[str]
    suggested_changes: dict = Field(default_factory=dict)
    review_result_id: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    provider_request_id: str = ""

    @model_validator(mode="after")
    def validate_decision_risk_consistency(self):
        if self.decision == "pass" and self.risk_level != "low":
            raise ValueError("pass reviews must have low risk")
        if self.decision == "needs_human_review" and self.risk_level == "low":
            raise ValueError("human-review decisions cannot have low risk")
        if self.decision == "block" and self.risk_level != "high":
            raise ValueError("blocked reviews must have high risk")
        return self


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
