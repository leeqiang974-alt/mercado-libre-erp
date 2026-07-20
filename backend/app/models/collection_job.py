from datetime import UTC, datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CollectionJobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    NEEDS_MANUAL_ACTION = "needs_manual_action"
    FAILED = "failed"


class CollectionJob(Base):
    __tablename__ = "collection_jobs"
    __table_args__ = (
        Index("ix_collection_jobs_site_identity", "target_site_id", "source_identity"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_url: Mapped[str] = mapped_column(Text)
    source_identity: Mapped[str | None] = mapped_column(String(256), nullable=True)
    target_site_id: Mapped[str] = mapped_column(String(8), default="MLM")
    status: Mapped[CollectionJobStatus] = mapped_column(default=CollectionJobStatus.PENDING)
    message: Mapped[str] = mapped_column(Text, default="")
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
