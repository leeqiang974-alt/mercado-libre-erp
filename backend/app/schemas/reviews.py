from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.drafts import ProductDraftCreate


class ReviewPricingContext(BaseModel):
    source_price: float
    source_currency: str
    target_currency: str
    exchange_rate: float
    purchase_extra_cost: float
    shipping_cost: float
    platform_fee_rate: float
    tax_rate: float
    profit_margin_rate: float
    rounding_increment: float
    landed_cost: float
    target_price: float


class ReviewListingContext(BaseModel):
    authorized_store_id: int
    site_id: str
    category_id: str
    listing_type_id: str
    fulfillment: str
    shipping_mode: str
    shipping_logistic_type: str
    attributes: list[dict] = Field(default_factory=list)


class DraftReviewSubject(BaseModel):
    draft: ProductDraftCreate
    pricing: ReviewPricingContext | None = None
    listing: ReviewListingContext | None = None


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
    price_config_id: int | None = None
    estimated_cost_amount: Decimal | None = None
    estimated_cost_currency: str = ""

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
    price_config_id: int | None = None
    estimated_cost_amount: Decimal | None = None
    estimated_cost_currency: str = ""
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


class ReviewJobBatchCreate(BaseModel):
    draft_ids: list[Annotated[int, Field(gt=0)]] = Field(min_length=1, max_length=50)
    acknowledge_provider_costs: bool

    @model_validator(mode="after")
    def validate_batch(self):
        if len(set(self.draft_ids)) != len(self.draft_ids):
            raise ValueError("draft_ids must be unique")
        if not self.acknowledge_provider_costs:
            raise ValueError("provider_cost_acknowledgement_required")
        return self


class ReviewJobRead(BaseModel):
    id: int
    batch_id: str
    product_draft_id: int
    draft_version: int
    status: str
    aggregate_review_result_id: int | None = None
    error_code: str = ""
    error_detail: dict = Field(default_factory=dict)
    created_at: datetime
    next_attempt_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class ReviewJobBatchItem(BaseModel):
    draft_id: int
    outcome: Literal["queued", "existing", "not_ready", "not_found"]
    errors: list[str] = Field(default_factory=list)
    job: ReviewJobRead | None = None


class ReviewJobBatchResponse(BaseModel):
    batch_id: str
    queued_count: int
    existing_count: int
    not_ready_count: int
    not_found_count: int
    items: list[ReviewJobBatchItem]
