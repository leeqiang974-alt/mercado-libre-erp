from enum import Enum

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ProductDraftStatus(str, Enum):
    DRAFT = "draft"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    PUBLISHED = "published"
    BLOCKED = "blocked"


class ProductDraft(Base):
    __tablename__ = "product_drafts"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_product_id: Mapped[int | None] = mapped_column(ForeignKey("source_products.id"), nullable=True)
    target_site_id: Mapped[str] = mapped_column(String(8), default="MLM")
    target_category_id: Mapped[str] = mapped_column(String(40), default="")
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    brand: Mapped[str] = mapped_column(String(120), default="")
    condition: Mapped[str] = mapped_column(String(40), default="new")
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(8), default="")
    stock: Mapped[int] = mapped_column(Integer, default=0)
    listing_type_id: Mapped[str] = mapped_column(String(40), default="")
    shipping_profile: Mapped[str] = mapped_column(String(80), default="")
    status: Mapped[ProductDraftStatus] = mapped_column(default=ProductDraftStatus.DRAFT)
    risk_status: Mapped[str] = mapped_column(String(40), default="unreviewed")
