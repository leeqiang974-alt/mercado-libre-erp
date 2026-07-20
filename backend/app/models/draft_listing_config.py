from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DraftListingConfig(Base):
    __tablename__ = "draft_listing_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_draft_id: Mapped[int] = mapped_column(
        ForeignKey("product_drafts.id"), unique=True, index=True
    )
    store_id: Mapped[int | None] = mapped_column(ForeignKey("stores.id"), nullable=True)
    site_id: Mapped[str] = mapped_column(String(8))
    category_id: Mapped[str] = mapped_column(String(40))
    listing_type_id: Mapped[str] = mapped_column(String(40))
    fulfillment: Mapped[str] = mapped_column(String(40), default="not_full")
    shipping_mode: Mapped[str] = mapped_column(String(40), default="")
    shipping_logistic_type: Mapped[str] = mapped_column(String(40), default="")
    attributes_json: Mapped[list[dict]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
