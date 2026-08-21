from app.schemas.drafts import ProductDraftCreate
from app.schemas.cbt_listing_config import CbtListingConfigUpsert
from app.schemas.publishing import ListingChoice
import re


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


CBT_REQUIRED_SHIPPING_ATTRIBUTES = {
    "PACKAGE_HEIGHT",
    "PACKAGE_LENGTH",
    "PACKAGE_WIDTH",
    "PACKAGE_WEIGHT",
}

_CBT_PACKAGE_ATTRIBUTE_UNITS = {
    "PACKAGE_HEIGHT": "cm",
    "PACKAGE_LENGTH": "cm",
    "PACKAGE_WIDTH": "cm",
    "PACKAGE_WEIGHT": "g",
}


def _normalize_cbt_attributes(attributes: list[dict]) -> list[dict]:
    """Convert editor shorthand into the values accepted by Global Selling."""
    normalized: list[dict] = []
    for raw in attributes:
        attribute = dict(raw)
        attribute_id = str(attribute.get("id", "")).strip().upper()
        value_name = str(attribute.get("value_name", "")).strip()
        if attribute_id == "ITEM_CONDITION" and value_name.casefold() == "new":
            # CBT category metadata exposes the official condition value.
            attribute["value_name"] = "New"
            attribute["value_id"] = attribute.get("value_id") or "2230284"
        elif attribute_id in _CBT_PACKAGE_ATTRIBUTE_UNITS and re.fullmatch(r"\d+(?:\.\d+)?", value_name):
            # Package attributes are number_unit fields. The compact UI accepts
            # a bare number but the marketplace request must include its unit.
            attribute["value_name"] = f"{value_name} {_CBT_PACKAGE_ATTRIBUTE_UNITS[attribute_id]}"
        normalized.append(attribute)
    return normalized


def build_cbt_global_item_payload(
    draft: ProductDraftCreate,
    config: CbtListingConfigUpsert,
) -> dict:
    """Build the traditional Global Selling /global/items request body.

    CBT is a parent seller account. Images and offer-specific data deliberately
    live inside each sites_to_sell entry, rather than at root level as they do
    for a local /items request.
    """
    if not config.category_id.startswith("CBT"):
        raise ValueError("Global Selling category ID must start with CBT.")
    if not config.family_name.strip():
        raise ValueError("family_name is required for a traditional CBT seller.")
    if not config.description.strip():
        raise ValueError("Description is required.")
    if not config.global_title.strip():
        raise ValueError("Global title is required.")
    if config.price_usd <= 0:
        raise ValueError("USD price must be greater than zero.")
    if config.available_quantity < 1:
        raise ValueError("Available quantity must be at least one.")
    if not config.sites_to_sell:
        raise ValueError("At least one Remote marketplace is required.")

    attributes = _normalize_cbt_attributes(
        [attribute.model_dump(exclude_none=True) for attribute in config.attributes]
    )
    attribute_ids = {str(attribute.get("id", "")).upper() for attribute in attributes}
    if "ITEM_CONDITION" not in attribute_ids:
        raise ValueError("Verified ITEM_CONDITION attribute is required.")
    missing_shipping = CBT_REQUIRED_SHIPPING_ATTRIBUTES - attribute_ids
    if missing_shipping:
        raise ValueError(
            "CBT package attributes are required: " + ", ".join(sorted(missing_shipping))
        )
    if "SELLER_SKU" not in attribute_ids:
        raise ValueError("SELLER_SKU attribute is required.")

    default_pictures = list(draft.image_urls or [])
    sites_to_sell: list[dict] = []
    for offer in config.sites_to_sell:
        picture_urls = offer.picture_urls or default_pictures
        if not picture_urls:
            raise ValueError(f"At least one picture is required for {offer.site_id}.")
        sites_to_sell.append(
            {
                "site_id": offer.site_id,
                "logistic_type": "remote",
                "listing_type_id": offer.listing_type_id,
                "title": offer.title,
                "pictures": [{"source": url} for url in picture_urls],
            }
        )

    return {
        "title": config.global_title,
        "family_name": config.family_name,
        "category_id": config.category_id,
        "currency_id": "USD",
        "price": config.price_usd,
        "available_quantity": config.available_quantity,
        # /global/items validates a root image collection in addition to each
        # Remote-market offer's pictures. Keep both from the same ordered
        # product image library.
        "pictures": [{"source": url} for url in default_pictures],
        # Traditional Global Selling expects an ItemDescription object here,
        # unlike a plain string in the draft/editor state.
        "description": build_description_payload(
            draft.model_copy(update={"description": config.description})
        ),
        "attributes": attributes,
        "sale_terms": [term.model_dump(exclude_none=True) for term in config.sale_terms],
        "sites_to_sell": sites_to_sell,
    }
