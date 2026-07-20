from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ProductDraftApproval(Base):
    __tablename__ = "product_draft_approvals"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_draft_id: Mapped[int] = mapped_column(
        ForeignKey("product_drafts.id"), unique=True, index=True
    )
    review_result_id: Mapped[int | None] = mapped_column(
        ForeignKey("review_results.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(40), default="approved")
    approved_by: Mapped[str] = mapped_column(String(120))
    note: Mapped[str] = mapped_column(Text, default="")
    draft_version: Mapped[int] = mapped_column(Integer, default=1)
    approved_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
