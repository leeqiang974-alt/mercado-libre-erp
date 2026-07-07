from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SourceProductStatus(str, Enum):
    PENDING = "pending"
    COLLECTED = "collected"
    NEEDS_MANUAL_ACTION = "needs_manual_action"
    FAILED = "failed"


class SourceProduct(Base):
    __tablename__ = "source_products"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(40), default="amazon_page")
    source_url: Mapped[str] = mapped_column(Text)
    asin: Mapped[str] = mapped_column(String(20), default="")
    raw_status: Mapped[SourceProductStatus] = mapped_column(default=SourceProductStatus.PENDING)
    collected_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    collection_error: Mapped[str] = mapped_column(Text, default="")
    raw_snapshot_reference: Mapped[str] = mapped_column(Text, default="")
