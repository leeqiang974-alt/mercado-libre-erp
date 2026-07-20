from datetime import UTC, datetime
from enum import Enum

from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ReviewDecision(str, Enum):
    PASS = "pass"
    NEEDS_HUMAN_REVIEW = "needs_human_review"
    BLOCK = "block"


class ReviewResult(Base):
    __tablename__ = "review_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_draft_id: Mapped[int] = mapped_column(ForeignKey("product_drafts.id"))
    provider: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(120), default="")
    prompt_version: Mapped[str] = mapped_column(String(80), default="")
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    provider_status: Mapped[str] = mapped_column(String(40), default="completed")
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provider_request_id: Mapped[str] = mapped_column(String(160), default="")
    price_config_id: Mapped[int | None] = mapped_column(
        ForeignKey("provider_model_prices.id"), nullable=True
    )
    estimated_cost_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(28, 8), nullable=True
    )
    estimated_cost_currency: Mapped[str] = mapped_column(String(3), default="")
    risk_level: Mapped[str] = mapped_column(String(40))
    decision: Mapped[ReviewDecision] = mapped_column()
    reasons_json: Mapped[dict] = mapped_column(JSON, default=dict)
    suggested_changes_json: Mapped[dict] = mapped_column(JSON, default=dict)
    draft_version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
