from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.models.meli_metadata_cache import MeliMetadataCache
from app.services.meli.metadata_cache import available_listing_types_key


def validate_store_category_listing_type(
    db: Session,
    store_id: int,
    category_id: str,
    listing_type_id: str,
    *,
    require_verified_metadata: bool,
    max_age_seconds: int = 900,
) -> list[str]:
    row = (
        db.query(MeliMetadataCache)
        .populate_existing()
        .filter(
            MeliMetadataCache.cache_key
            == available_listing_types_key(store_id, category_id)
        )
        .one_or_none()
    )
    if not _is_fresh_verified_payload(
        row,
        store_id=store_id,
        category_id=category_id,
        max_age_seconds=max_age_seconds,
    ):
        return ["listing_types_not_verified"] if require_verified_metadata else []
    available_ids = {
        item["id"] for item in row.payload_json["listing_types"]
    }
    if listing_type_id.strip().lower() not in available_ids:
        return ["listing_type_not_available"]
    return []


def _is_fresh_verified_payload(
    row: MeliMetadataCache | None,
    *,
    store_id: int,
    category_id: str,
    max_age_seconds: int,
) -> bool:
    if row is None:
        return False
    payload = row.payload_json or {}
    if (
        payload.get("verified") is not True
        or payload.get("store_id") != store_id
        or str(payload.get("category_id") or "").strip().upper()
        != category_id.strip().upper()
    ):
        return False
    listing_types = payload.get("listing_types")
    if not isinstance(listing_types, list) or not all(
        isinstance(item, dict)
        and isinstance(item.get("id"), str)
        and bool(item["id"].strip())
        for item in listing_types
    ):
        return False
    refreshed_at = row.refreshed_at
    if refreshed_at.tzinfo is None:
        refreshed_at = refreshed_at.replace(tzinfo=UTC)
    return refreshed_at >= datetime.now(UTC) - timedelta(
        seconds=max(0, max_age_seconds)
    )
