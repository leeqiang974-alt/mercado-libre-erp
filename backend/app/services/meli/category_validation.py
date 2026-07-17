from sqlalchemy.orm import Session

from app.services.meli.metadata_cache import category_attributes_key, get_cached_metadata


def validate_category_attributes(
    db: Session,
    category_id: str,
    attributes: list[dict],
    *,
    require_verified_metadata: bool,
) -> list[str]:
    cached = get_cached_metadata(db, category_attributes_key(category_id))
    if cached is None:
        return ["category_attributes_not_verified"] if require_verified_metadata else []

    provided_ids = {
        str(attribute.get("id", "")).strip().upper()
        for attribute in attributes
        if _has_value(attribute)
    }
    missing = []
    for definition in cached.get("attributes", []):
        attribute_id = str(definition.get("id", "")).strip().upper()
        tags = definition.get("tags") or {}
        if attribute_id and tags.get("required") is True and attribute_id not in provided_ids:
            missing.append(f"required_category_attribute_missing:{attribute_id}")
    return missing


def _has_value(attribute: dict) -> bool:
    return any(
        value not in (None, "", {})
        for value in (
            attribute.get("value_id"),
            attribute.get("value_name"),
            attribute.get("value_struct"),
        )
    )
