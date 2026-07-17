from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator


class DraftPricingUpsert(BaseModel):
    source_price: float = Field(gt=0)
    source_currency: str = Field(min_length=3, max_length=8)
    target_currency: str = Field(min_length=3, max_length=8)
    exchange_rate: float = Field(gt=0)
    purchase_extra_cost: float = Field(default=0, ge=0)
    shipping_cost: float = Field(default=0, ge=0)
    platform_fee_rate: float = Field(default=0, ge=0, lt=1)
    tax_rate: float = Field(default=0, ge=0, lt=1)
    profit_margin_rate: float = Field(default=0, ge=0, lt=1)
    rounding_increment: float = Field(default=1, gt=0)

    @field_validator("source_currency", "target_currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.strip().upper()

    @model_validator(mode="after")
    def validate_rate_sum(self):
        total = self.platform_fee_rate + self.tax_rate + self.profit_margin_rate
        if total >= 1:
            raise ValueError("Platform fee, tax, and profit rates must total less than 100%.")
        return self


class DraftPricingRead(DraftPricingUpsert):
    id: int
    product_draft_id: int
    landed_cost: float
    target_price: float
    created_at: datetime
    updated_at: datetime
