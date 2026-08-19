from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DraftPricingConfig(Base):
    __tablename__ = "draft_pricing_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_draft_id: Mapped[int] = mapped_column(
        ForeignKey("product_drafts.id"), unique=True, index=True
    )
    source_price: Mapped[float] = mapped_column(Float)
    source_currency: Mapped[str] = mapped_column(String(8))
    target_currency: Mapped[str] = mapped_column(String(8))
    cost_currency: Mapped[str] = mapped_column(String(8), default="CNY")
    purchase_cost: Mapped[float] = mapped_column(Float, default=0)
    domestic_shipping_cost: Mapped[float] = mapped_column(Float, default=0)
    exchange_rate: Mapped[float] = mapped_column(Float)
    purchase_extra_cost: Mapped[float] = mapped_column(Float, default=0)
    shipping_cost: Mapped[float] = mapped_column(Float, default=0)
    platform_fee_rate: Mapped[float] = mapped_column(Float, default=0)
    tax_rate: Mapped[float] = mapped_column(Float, default=0)
    profit_margin_rate: Mapped[float] = mapped_column(Float, default=0)
    rounding_increment: Mapped[float] = mapped_column(Float, default=1)
    landed_cost: Mapped[float] = mapped_column(Float)
    target_price: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
