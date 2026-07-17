from app.schemas.drafts import ProductDraftCreate
from app.schemas.publishing import ListingChoice


def build_item_payload(draft: ProductDraftCreate, listing_choice: ListingChoice) -> dict:
    if listing_choice.fulfillment.lower() == "full":
        raise ValueError("FULL fulfillment is excluded from this system.")
    if listing_choice.site_id != draft.target_site_id:
        raise ValueError("Listing choice site must match draft target site.")
    if not listing_choice.listing_type_id:
        raise ValueError("Listing type is required.")
    if not draft.target_category_id:
        raise ValueError("Category is required.")
    if draft.price is None or draft.price <= 0:
        raise ValueError("Target price must be greater than zero.")
    if not draft.currency:
        raise ValueError("Target currency is required.")
    if draft.stock < 1:
        raise ValueError("Available quantity must be at least one.")
    if not draft.image_urls:
        raise ValueError("At least one picture is required.")
    payload = {
        "site_id": draft.target_site_id,
        "title": draft.title,
        "category_id": draft.target_category_id,
        "price": draft.price,
        "currency_id": draft.currency,
        "available_quantity": draft.stock,
        "buying_mode": "buy_it_now",
        "condition": draft.condition,
        "listing_type_id": listing_choice.listing_type_id,
        "description": {"plain_text": draft.description},
        "pictures": [{"source": url} for url in draft.image_urls],
    }
    if listing_choice.attributes:
        payload["attributes"] = listing_choice.attributes
    return payload
