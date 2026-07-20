from datetime import datetime
from decimal import Decimal
import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ProviderModelPriceCreate(BaseModel):
    provider: Literal["claude", "nvidia"]
    model: str = Field(min_length=1, max_length=160)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    input_price_per_million: Decimal = Field(ge=0, max_digits=18, decimal_places=6)
    output_price_per_million: Decimal = Field(ge=0, max_digits=18, decimal_places=6)

    @field_validator("model")
    @classmethod
    def normalize_model(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("model is required")
        return normalized

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        normalized = value.strip().upper()
        if re.fullmatch(r"[A-Z]{3}", normalized) is None:
            raise ValueError("currency must be a three-letter code")
        return normalized


class ProviderModelPriceRead(BaseModel):
    id: int
    provider: str
    model: str
    version: int
    currency: str
    input_price_per_million: Decimal
    output_price_per_million: Decimal
    active: bool
    created_at: datetime
