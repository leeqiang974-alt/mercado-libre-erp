from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.drafts import ProductDraftRead


class DraftPricingUpsert(BaseModel):
    # Amazon evidence remains immutable reference data. The operator's own CNY
    # procurement and domestic-delivery costs are the only listing cost inputs.
    source_price: float = Field(gt=0)
    source_currency: str = Field(min_length=3, max_length=8)
    target_currency: str = Field(min_length=3, max_length=8)
    cost_currency: str = Field(default="CNY", min_length=3, max_length=8)
    purchase_cost: float = Field(gt=0)
    domestic_shipping_cost: float = Field(default=0, ge=0)
    exchange_rate: float = Field(gt=0)
    profit_margin_rate: float = Field(default=0, ge=0, lt=10)
    rounding_increment: float = Field(default=0.01, gt=0)

    # Retained in responses for historic records. The Global Selling pricing
    # workflow never uses these marketplace-cost fields.
    purchase_extra_cost: float = Field(default=0, ge=0)
    shipping_cost: float = Field(default=0, ge=0)
    platform_fee_rate: float = Field(default=0, ge=0, lt=1)
    tax_rate: float = Field(default=0, ge=0, lt=1)

    @field_validator("source_currency", "target_currency", "cost_currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.strip().upper()

    @model_validator(mode="after")
    def validate_global_selling_pricing(self):
        if self.cost_currency != "CNY":
            raise ValueError("Global Selling procurement costs must be entered in CNY.")
        if any((self.purchase_extra_cost, self.shipping_cost, self.platform_fee_rate, self.tax_rate)):
            raise ValueError(
                "Marketplace fees, taxes, and international shipping are not per-item Global Selling price inputs."
            )
        return self


class DraftPricingRead(DraftPricingUpsert):
    id: int
    product_draft_id: int
    landed_cost: float
    target_price: float
    draft_content_version: int
    draft: ProductDraftRead
    created_at: datetime
    updated_at: datetime
