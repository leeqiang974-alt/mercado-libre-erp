from pydantic import BaseModel, Field


class AttributeSuggestion(BaseModel):
    source_name: str
    source_value: str
    attribute_id: str
    attribute_name: str
    value_name: str
    value_id: str | None = None
    confidence: float = Field(ge=0, le=1)
    match_reason: str
    required: bool = False
    variation_attribute: bool = False
    can_apply: bool = False


class AttributeSuggestionRead(BaseModel):
    product_draft_id: int
    category_id: str
    source_variant_asin: str = ""
    listing_strategy: str = "one_source_asin_per_item"
    suggestions: list[AttributeSuggestion] = Field(default_factory=list)
    unmatched_source_attributes: dict[str, str] = Field(default_factory=dict)
