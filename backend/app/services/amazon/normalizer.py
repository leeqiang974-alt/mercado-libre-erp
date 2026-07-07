from app.schemas.drafts import ProductDraftCreate


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
    return ProductDraftCreate(
        title=parsed.get("title", ""),
        description="\n\n".join(description_parts),
        brand=parsed.get("brand", ""),
        target_site_id=target_site_id,
        price=price.get("amount"),
        currency=price.get("currency", ""),
        stock=1,
        image_urls=parsed.get("images", []),
    )
