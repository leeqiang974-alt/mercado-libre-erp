from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Index, Integer, Numeric, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ProviderModelPrice(Base):
    __tablename__ = "provider_model_prices"
    __table_args__ = (
        UniqueConstraint("provider", "model", "version", name="uq_provider_model_price_version"),
        Index(
            "uq_provider_model_prices_active",
            "provider",
            "model",
            unique=True,
            postgresql_where=text("active"),
            sqlite_where=text("active"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(20), index=True)
    model: Mapped[str] = mapped_column(String(160), index=True)
    version: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    input_price_per_million: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    output_price_per_million: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
