from datetime import UTC, datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String
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
    risk_level: Mapped[str] = mapped_column(String(40))
    decision: Mapped[ReviewDecision] = mapped_column()
    reasons_json: Mapped[dict] = mapped_column(JSON, default=dict)
    suggested_changes_json: Mapped[dict] = mapped_column(JSON, default=dict)
    draft_version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
