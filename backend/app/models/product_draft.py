from enum import Enum

from sqlalchemy import Float, ForeignKey, Index, Integer, JSON, String, Text, text
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
    __table_args__ = (
        Index(
            "uq_product_drafts_source_variant_site",
            "source_product_id",
            "source_variant_asin",
            "target_site_id",
            unique=True,
            postgresql_where=text("source_variant_asin <> ''"),
            sqlite_where=text("source_variant_asin <> ''"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_product_id: Mapped[int | None] = mapped_column(ForeignKey("source_products.id"), nullable=True)
    source_variant_asin: Mapped[str] = mapped_column(String(10), default="")
    source_variant_attributes_json: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    target_site_id: Mapped[str] = mapped_column(String(8), default="MLM")
    target_category_id: Mapped[str] = mapped_column(String(40), default="")
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    brand: Mapped[str] = mapped_column(String(120), default="")
    condition: Mapped[str] = mapped_column(String(40), default="new")
    source_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_currency: Mapped[str] = mapped_column(String(8), default="")
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(8), default="")
    stock: Mapped[int] = mapped_column(Integer, default=0)
    listing_type_id: Mapped[str] = mapped_column(String(40), default="")
    shipping_profile: Mapped[str] = mapped_column(String(80), default="")
    image_urls_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    status: Mapped[ProductDraftStatus] = mapped_column(default=ProductDraftStatus.DRAFT)
    risk_status: Mapped[str] = mapped_column(String(40), default="unreviewed")
    content_version: Mapped[int] = mapped_column(Integer, default=1)
