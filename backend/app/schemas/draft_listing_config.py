from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator


SUPPORTED_SHIPPING_MODES = {"me2", "me1", "not_specified"}
SUPPORTED_LISTING_TYPE_IDS = {"gold_special", "gold_pro"}
SUPPORTED_NON_FULL_LOGISTIC_TYPES = {
    "drop_off",
    "cross_docking",
    "xd_drop_off",
    "self_service",
    "turbo",
    "default",
    "not_specified",
}


class ListingAttributeValue(BaseModel):
    id: str
    value_name: str = ""
    value_id: str | None = None

    @field_validator("id")
    @classmethod
    def require_attribute_id(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("Attribute ID is required.")
        return normalized

    @model_validator(mode="after")
    def require_value(self):
        if not self.value_name.strip() and not (self.value_id or "").strip():
            raise ValueError("Attribute value_name or value_id is required.")
        self.value_name = self.value_name.strip()
        self.value_id = (self.value_id or "").strip() or None
        return self


class DraftListingConfigUpsert(BaseModel):
    site_id: str
    store_id: int | None = None
    category_id: str
    listing_type_id: str
    fulfillment: str = "not_full"
    shipping_mode: str = ""
    shipping_logistic_type: str = ""
    attributes: list[ListingAttributeValue] = Field(default_factory=list)

    @field_validator("listing_type_id")
    @classmethod
    def require_classic_or_premium(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in SUPPORTED_LISTING_TYPE_IDS:
            raise ValueError("Only Mercado Libre Classic or Premium listing types are supported.")
        return normalized

    @field_validator("fulfillment")
    @classmethod
    def reject_full_fulfillment(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized == "full":
            raise ValueError("FULL fulfillment is excluded from this system.")
        return normalized

    @field_validator("shipping_mode")
    @classmethod
    def validate_shipping_mode(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized and normalized not in SUPPORTED_SHIPPING_MODES:
            raise ValueError("Unsupported non-FULL shipping mode.")
        return normalized

    @field_validator("shipping_logistic_type")
    @classmethod
    def validate_shipping_logistic_type(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized == "fulfillment":
            raise ValueError("FULL fulfillment is excluded from this system.")
        if normalized and normalized not in SUPPORTED_NON_FULL_LOGISTIC_TYPES:
            raise ValueError("Unsupported non-FULL logistic type.")
        return normalized

    @model_validator(mode="after")
    def require_complete_shipping_selection(self):
        if bool(self.shipping_mode) != bool(self.shipping_logistic_type):
            raise ValueError("Shipping mode and logistic type must be selected together.")
        if self.store_id is not None and not self.shipping_mode:
            raise ValueError("A connected store requires a non-FULL shipping selection.")
        if self.shipping_mode and self.store_id is None:
            raise ValueError("Shipping selection must be bound to a connected store.")
        attribute_ids = [attribute.id for attribute in self.attributes]
        if len(attribute_ids) != len(set(attribute_ids)):
            raise ValueError("Listing attribute IDs must be unique.")
        return self


class DraftListingConfigRead(BaseModel):
    id: int
    product_draft_id: int
    site_id: str
    store_id: int | None = None
    category_id: str
    listing_type_id: str
    fulfillment: str
    shipping_mode: str
    shipping_logistic_type: str
    attributes: list[ListingAttributeValue] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
