from datetime import UTC, datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.types import TypeDecorator
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CollectionJobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    NEEDS_MANUAL_ACTION = "needs_manual_action"
    FAILED = "failed"


class CollectionJobStatusType(TypeDecorator[str]):
    """Store collection statuses as VARCHAR and read legacy uppercase values."""

    impl = String(32)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, CollectionJobStatus):
            return value.value
        text = str(value).strip()
        try:
            return CollectionJobStatus[text.upper()].value
        except KeyError:
            return text.lower()

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        text = str(value).strip()
        try:
            return CollectionJobStatus(text.lower())
        except ValueError:
            return CollectionJobStatus[text.upper()]


class CollectionJob(Base):
    __tablename__ = "collection_jobs"
    __table_args__ = (
        Index("ix_collection_jobs_site_identity", "target_site_id", "source_identity"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_url: Mapped[str] = mapped_column(Text)
    source_identity: Mapped[str | None] = mapped_column(String(256), nullable=True)
    target_site_id: Mapped[str] = mapped_column(String(8), default="MLM")
    status: Mapped[CollectionJobStatus] = mapped_column(
        CollectionJobStatusType(),
        default=CollectionJobStatus.PENDING,
    )
    message: Mapped[str] = mapped_column(Text, default="")
    campaign_id: Mapped[int | None] = mapped_column(ForeignKey("keyword_collection_campaigns.id"), nullable=True, index=True)
    campaign_keyword: Mapped[str | None] = mapped_column(String(240), nullable=True)
    source_product_id: Mapped[int | None] = mapped_column(
        ForeignKey("source_products.id"), nullable=True
    )
    draft_id: Mapped[int | None] = mapped_column(ForeignKey("product_drafts.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    next_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    claimed_by: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
