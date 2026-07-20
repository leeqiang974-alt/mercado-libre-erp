from datetime import UTC, datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ReviewJobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    FAILED = "failed"


class ReviewJob(Base):
    __tablename__ = "review_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[str] = mapped_column(String(36), index=True)
    product_draft_id: Mapped[int] = mapped_column(ForeignKey("product_drafts.id"), index=True)
    requested_by: Mapped[str] = mapped_column(String(120), default="operator")
    draft_version: Mapped[int] = mapped_column(default=1)
    baseline_review_result_id: Mapped[int | None] = mapped_column(
        ForeignKey("review_results.id"), nullable=True
    )
    active_key: Mapped[str | None] = mapped_column(String(80), unique=True, nullable=True)
    status: Mapped[ReviewJobStatus] = mapped_column(default=ReviewJobStatus.PENDING)
    aggregate_review_result_id: Mapped[int | None] = mapped_column(
        ForeignKey("review_results.id"), nullable=True
    )
    error_code: Mapped[str] = mapped_column(String(160), default="")
    error_detail_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
