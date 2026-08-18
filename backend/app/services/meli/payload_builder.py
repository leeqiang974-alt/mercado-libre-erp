from app.schemas.drafts import ProductDraftCreate
from app.schemas.publishing import ListingChoice


SUPPORTED_SHIPPING_MODES = {"me2", "me1", "not_specified"}
SUPPORTED_NON_FULL_LOGISTIC_TYPES = {
    "drop_off",
    "cross_docking",
    "xd_drop_off",
    "self_service",
    "turbo",
    "default",
    "not_specified",
}


def build_item_payload(
    draft: ProductDraftCreate,
    listing_choice: ListingChoice,
    shipping_mode: str | None = None,
    shipping_logistic_type: str | None = None,
    seller_custom_field: str = "",
) -> dict:
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
    if not draft.description.strip():
        raise ValueError("Description is required.")
    item_condition = next(
        (
            attribute
            for attribute in listing_choice.attributes
            if str(attribute.get("id", "")).strip().upper() == "ITEM_CONDITION"
            and any(
                attribute.get(key) not in (None, "", {})
                for key in ("value_id", "value_name", "value_struct")
            )
        ),
        None,
    )
    if item_condition is None and not draft.condition.strip():
        raise ValueError("Verified ITEM_CONDITION attribute is required.")
    if shipping_mode and shipping_mode not in SUPPORTED_SHIPPING_MODES:
        raise ValueError("Unsupported non-FULL shipping mode.")
    if shipping_logistic_type and shipping_logistic_type not in SUPPORTED_NON_FULL_LOGISTIC_TYPES:
        raise ValueError("Unsupported non-FULL logistic type.")
    if bool(shipping_mode) != bool(shipping_logistic_type):
        raise ValueError("Shipping mode and logistic type must be selected together.")
    payload = {
        "site_id": draft.target_site_id,
        "title": draft.title,
        "category_id": draft.target_category_id,
        "price": draft.price,
        "currency_id": draft.currency,
        "available_quantity": draft.stock,
        "buying_mode": "buy_it_now",
        "listing_type_id": listing_choice.listing_type_id,
        "pictures": [{"source": url} for url in draft.image_urls],
    }
    if listing_choice.attributes:
        payload["attributes"] = listing_choice.attributes
    if item_condition is None and draft.condition.strip():
        # Backward-compatible direct requests; saved configurations use ITEM_CONDITION.
        payload["condition"] = draft.condition.strip().lower()
    if shipping_mode:
        payload["shipping"] = {
            "mode": shipping_mode,
            "logistic_type": shipping_logistic_type,
            "local_pick_up": False,
            "free_shipping": False,
        }
        if shipping_mode == "me2":
            payload["shipping"]["free_methods"] = []
    if seller_custom_field:
        payload["seller_custom_field"] = seller_custom_field
    return payload


def build_description_payload(draft: ProductDraftCreate) -> dict[str, str]:
    description = draft.description.strip()
    if not description:
        raise ValueError("Description is required.")
    return {"plain_text": description}
