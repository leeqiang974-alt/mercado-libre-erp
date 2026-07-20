import re
import unicodedata

from sqlalchemy.orm import Session

from app.services.meli.metadata_cache import category_attributes_key, get_cached_metadata


def validate_category_attributes(
    db: Session,
    category_id: str,
    attributes: list[dict],
    *,
    require_verified_metadata: bool,
    require_item_condition: bool = False,
) -> list[str]:
    cached = get_cached_metadata(db, category_attributes_key(category_id))
    raw_definitions = cached.get("attributes") if cached else None
    metadata_verified = (
        isinstance(raw_definitions, list)
        and cached.get("verified") is True
        and _definitions_are_valid(raw_definitions)
    )
    if not metadata_verified:
        return ["category_attributes_not_verified"] if require_verified_metadata else []

    malformed = [attribute for attribute in attributes if not isinstance(attribute, dict)]
    if malformed:
        return ["category_attribute_malformed"]
    provided_ids = {
        str(attribute.get("id", "")).strip().upper()
        for attribute in attributes
        if _has_value(attribute)
    }
    missing = []
    definitions = {
        str(definition.get("id", "")).strip().upper(): definition
        for definition in raw_definitions
        if isinstance(definition, dict) and str(definition.get("id", "")).strip()
    }
    if require_item_condition:
        if "ITEM_CONDITION" not in definitions:
            missing.append("item_condition_attribute_not_verified")
        elif "ITEM_CONDITION" not in provided_ids:
            missing.append("required_category_attribute_missing:ITEM_CONDITION")
    for attribute_id, definition in definitions.items():
        tags = definition.get("tags") or {}
        if (
            tags.get("required") is True or tags.get("catalog_required") is True
        ) and attribute_id not in provided_ids:
            missing.append(f"required_category_attribute_missing:{attribute_id}")
    seen_ids: set[str] = set()
    for attribute in attributes:
        attribute_id = str(attribute.get("id", "")).strip().upper()
        if not attribute_id or not _has_value(attribute):
            continue
        if attribute_id in seen_ids:
            missing.append(f"category_attribute_duplicate:{attribute_id}")
            continue
        seen_ids.add(attribute_id)
        definition = definitions.get(attribute_id)
        if definition is None:
            missing.append(f"category_attribute_unknown:{attribute_id}")
            continue
        value_id = str(attribute.get("value_id") or "").strip()
        value_name = str(attribute.get("value_name") or "").strip()
        allowed_values = definition.get("values")
        allowed_by_id = {
            str(value.get("id")): str(value.get("name") or "")
            for value in allowed_values
            if isinstance(value, dict) and value.get("id") is not None
        } if isinstance(allowed_values, list) else {}
        if value_id:
            if not allowed_by_id:
                missing.append(f"category_attribute_value_id_unverifiable:{attribute_id}")
                continue
            canonical_name = allowed_by_id.get(value_id)
            if canonical_name is None:
                missing.append(f"category_attribute_value_id_invalid:{attribute_id}")
            elif value_name and _normalize(value_name) != _normalize(canonical_name):
                missing.append(f"category_attribute_value_name_mismatch:{attribute_id}")
            continue
        if not value_id and allowed_by_id and str(definition.get("value_type", "")).lower() == "list":
            matching_names = [
                item_id
                for item_id, item_name in allowed_by_id.items()
                if _normalize(item_name) == _normalize(value_name)
            ]
            if matching_names:
                missing.append(f"category_attribute_value_id_required:{attribute_id}")
            elif not (definition.get("tags") or {}).get("variation_attribute"):
                missing.append(f"category_attribute_value_name_invalid:{attribute_id}")
    return missing


def canonical_item_condition(attributes: list[dict]) -> str:
    condition = next(
        (
            attribute
            for attribute in attributes
            if isinstance(attribute, dict)
            and str(attribute.get("id", "")).strip().upper() == "ITEM_CONDITION"
        ),
        None,
    )
    if condition is None:
        return ""
    known_values = {
        "2230284": "new",
        "2230581": "used",
        "2230582": "refurbished",
    }
    value_id = str(condition.get("value_id") or "").strip()
    if value_id in known_values:
        return known_values[value_id]
    return str(condition.get("value_name") or "").strip().lower()[:40]


def _has_value(attribute: dict) -> bool:
    return any(
        value not in (None, "", {})
        for value in (
            attribute.get("value_id"),
            attribute.get("value_name"),
            attribute.get("value_struct"),
        )
    )


def _normalize(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", ascii_value.lower())


def _definitions_are_valid(definitions: list[object]) -> bool:
    definition_ids: set[str] = set()
    for definition in definitions:
        if not isinstance(definition, dict):
            return False
        attribute_id = str(definition.get("id") or "").strip().upper()
        if not attribute_id or attribute_id in definition_ids:
            return False
        definition_ids.add(attribute_id)
        if "tags" in definition and not isinstance(definition["tags"], dict):
            return False
        if "values" in definition:
            values = definition["values"]
            if not isinstance(values, list):
                return False
            if any(
                not isinstance(value, dict) or value.get("id") is None
                for value in values
            ):
                return False
    return True
