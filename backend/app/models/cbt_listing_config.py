from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CbtListingConfig(Base):
    """Traditional Global Selling configuration for one CBT product draft."""

    __tablename__ = "cbt_listing_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_draft_id: Mapped[int] = mapped_column(
        ForeignKey("product_drafts.id"), unique=True, index=True
    )
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), index=True)
    category_id: Mapped[str] = mapped_column(String(40))
    family_name: Mapped[str] = mapped_column(String(200))
    global_title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    price_usd: Mapped[float] = mapped_column()
    available_quantity: Mapped[int] = mapped_column(Integer)
    attributes_json: Mapped[list[dict]] = mapped_column(JSON, default=list)
    sale_terms_json: Mapped[list[dict]] = mapped_column(JSON, default=list)
    sites_to_sell_json: Mapped[list[dict]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
