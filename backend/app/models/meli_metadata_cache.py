from datetime import UTC, datetime

from sqlalchemy import DateTime, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MeliMetadataCache(Base):
    __tablename__ = "meli_metadata_cache"

    id: Mapped[int] = mapped_column(primary_key=True)
    cache_key: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    refreshed_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
