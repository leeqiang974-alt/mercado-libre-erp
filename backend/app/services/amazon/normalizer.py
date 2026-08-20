import re

from app.schemas.drafts import ProductDraftCreate
from app.services.drafts import sanitize_unbranded_description
from app.services.amazon.media import prepare_listing_title, select_listing_images
from app.services.meli.sites import expected_currency


def _remove_phrase(value: str, phrase: str) -> str:
    if not phrase.strip():
        return value
    return re.sub(
        rf"(?<![A-Za-z0-9]){re.escape(phrase.strip())}(?![A-Za-z0-9])",
        "",
        value,
        flags=re.IGNORECASE,
    )


def normalize_amazon_product(parsed: dict, target_site_id: str) -> ProductDraftCreate:
    description_parts = []
    if parsed.get("description"):
        description_parts.append(parsed["description"])
    if parsed.get("bullets"):
        description_parts.append("\n".join(f"- {bullet}" for bullet in parsed["bullets"]))
    if parsed.get("technical_details"):
        description_parts.append(
            "\n".join(f"{key}: {value}" for key, value in parsed["technical_details"].items())
        )
    price = parsed.get("price", {})
    source_brand = str(parsed.get("brand") or "").strip()
    return ProductDraftCreate(
        title=prepare_listing_title(parsed.get("title", ""), source_brand),
        description=sanitize_unbranded_description("\n\n".join(description_parts), source_brand),
        brand=parsed.get("brand", "")[:120],
        target_site_id=target_site_id,
        source_price=price.get("amount"),
        source_currency=price.get("currency", ""),
        price=None,
        currency=expected_currency(target_site_id),
        stock=0,
        image_urls=select_listing_images(list(parsed.get("images") or [])),
    )
