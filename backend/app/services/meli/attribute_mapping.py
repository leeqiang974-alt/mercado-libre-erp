import re
import unicodedata

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.product_draft import ProductDraft
from app.schemas.attribute_mapping import AttributeSuggestion, AttributeSuggestionRead
from app.services.meli.metadata_cache import category_attributes_key, get_cached_metadata


ATTRIBUTE_ALIASES = {
    "brand": {"brand", "brandname", "marca"},
    "color": {
        "color",
        "colorname",
        "colorprincipal",
        "colour",
        "maincolor",
        "primarycolor",
        "cor",
    },
    "model": {"model", "modelname", "modelo"},
    "size": {
        "clothingsize",
        "shoesize",
        "size",
        "sizename",
        "talla",
        "tamano",
        "tamanho",
    },
}


def suggest_draft_category_attributes(
    db: Session,
    product_draft_id: int,
    category_id: str,
) -> AttributeSuggestionRead:
    draft = db.get(ProductDraft, product_draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Product draft not found.")
    normalized_category_id = category_id.strip().upper()
    cached = get_cached_metadata(db, category_attributes_key(normalized_category_id))
    if cached is None or cached.get("verified") is not True:
        raise HTTPException(status_code=409, detail="category_attributes_not_verified")

    source_attributes = dict(draft.source_variant_attributes_json or {})
    if draft.brand and not any(_semantic_group(name) == "brand" for name in source_attributes):
        source_attributes["Brand"] = draft.brand

    definitions = [
        definition
        for definition in cached.get("attributes", [])
        if isinstance(definition, dict) and not (definition.get("tags") or {}).get("hidden")
    ]
    suggestions: list[AttributeSuggestion] = []
    unmatched: dict[str, str] = {}
    used_definition_ids: set[str] = set()
    for source_name, source_value in source_attributes.items():
        match = _best_definition_match(source_name, definitions, used_definition_ids)
        if match is None:
            unmatched[str(source_name)] = str(source_value)
            continue
        definition, confidence, reason = match
        attribute_id = str(definition.get("id", "")).strip().upper()
        value_name = str(source_value).strip()
        value_id = _matching_value_id(value_name, definition.get("values"))
        value_type = str(definition.get("value_type", "")).strip().lower()
        tags = definition.get("tags") or {}
        can_apply = bool(value_name and (value_type != "list" or value_id))
        suggestions.append(
            AttributeSuggestion(
                source_name=str(source_name),
                source_value=value_name,
                attribute_id=attribute_id,
                attribute_name=str(definition.get("name") or attribute_id),
                value_name=value_name,
                value_id=value_id,
                confidence=confidence,
                match_reason=reason,
                required=bool(tags.get("required") or tags.get("catalog_required")),
                variation_attribute=bool(tags.get("variation_attribute")),
                can_apply=can_apply,
            )
        )
        used_definition_ids.add(attribute_id)

    return AttributeSuggestionRead(
        product_draft_id=draft.id,
        category_id=normalized_category_id,
        source_variant_asin=draft.source_variant_asin,
        suggestions=suggestions,
        unmatched_source_attributes=unmatched,
    )


def _best_definition_match(
    source_name: str,
    definitions: list[dict],
    used_definition_ids: set[str],
) -> tuple[dict, float, str] | None:
    source_normalized = _compact(source_name)
    source_group = _semantic_group(source_name)
    exact: list[dict] = []
    aliases: list[dict] = []
    for definition in definitions:
        attribute_id = str(definition.get("id", "")).strip().upper()
        if not attribute_id or attribute_id in used_definition_ids:
            continue
        names = [attribute_id, str(definition.get("name", ""))]
        if source_normalized and any(_compact(name) == source_normalized for name in names):
            exact.append(definition)
        elif source_group and any(_semantic_group(name) == source_group for name in names):
            aliases.append(definition)
    if len(exact) == 1:
        return exact[0], 1.0, "exact_attribute_name"
    if len(aliases) == 1:
        return aliases[0], 0.95, "semantic_attribute_alias"
    return None


def _matching_value_id(value_name: str, values: object) -> str | None:
    if not isinstance(values, list):
        return None
    normalized = _compact(value_name)
    matches = [
        str(value.get("id"))
        for value in values
        if isinstance(value, dict)
        and value.get("id") is not None
        and _compact(str(value.get("name", ""))) == normalized
    ]
    return matches[0] if len(matches) == 1 else None


def _semantic_group(value: str) -> str:
    compact = "".join(_words(value))
    for group, aliases in ATTRIBUTE_ALIASES.items():
        if compact in aliases:
            return group
    return ""


def _compact(value: str) -> str:
    return "".join(_words(value))


def _words(value: str) -> list[str]:
    ascii_value = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode()
    return [part for part in re.split(r"[^a-z0-9]+", ascii_value.lower()) if part]
