from datetime import UTC, datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PublishJobStatus(str, Enum):
    PENDING = "pending"
    VALIDATING = "validating"
    PUBLISHED = "published"
    FAILED = "failed"
    BLOCKED = "blocked"


class PublishJob(Base):
    __tablename__ = "publish_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_draft_id: Mapped[int] = mapped_column(ForeignKey("product_drafts.id"))
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"))
    requested_by: Mapped[str] = mapped_column(String(120))
    status: Mapped[PublishJobStatus] = mapped_column(default=PublishJobStatus.PENDING)
    request_summary_json: Mapped[dict] = mapped_column(JSON, default=dict)
    response_summary_json: Mapped[dict] = mapped_column(JSON, default=dict)
    meli_item_id: Mapped[str] = mapped_column(String(80), default="")
    permalink: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
