from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.meli_metadata_cache import MeliMetadataCache


def listing_types_key(site_id: str) -> str:
    return f"listing_types:{site_id}"


def category_attributes_key(category_id: str) -> str:
    return f"category_attributes:{category_id}"


def get_cached_metadata(db: Session, cache_key: str) -> dict | None:
    row = db.query(MeliMetadataCache).filter(MeliMetadataCache.cache_key == cache_key).one_or_none()
    return row.payload_json if row else None


def upsert_cached_metadata(db: Session, cache_key: str, payload: dict) -> MeliMetadataCache:
    row = db.query(MeliMetadataCache).filter(MeliMetadataCache.cache_key == cache_key).one_or_none()
    if row is None:
        row = MeliMetadataCache(cache_key=cache_key)
        db.add(row)
    row.payload_json = payload
    row.refreshed_at = datetime.now(UTC)
    db.commit()
    db.refresh(row)
    return row
