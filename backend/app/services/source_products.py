from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.source_product import SourceProduct, SourceProductStatus


def create_source_product(
    db: Session,
    source_url: str,
    status: SourceProductStatus,
    collection_error: str = "",
) -> SourceProduct:
    model = SourceProduct(
        source_url=source_url,
        raw_status=status,
        collected_at=datetime.now(UTC) if status == SourceProductStatus.COLLECTED else None,
        collection_error=collection_error,
    )
    db.add(model)
    db.flush()
    return model
