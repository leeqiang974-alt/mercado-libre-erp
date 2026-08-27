from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.drafts import ProductDraftRead


class DraftContentGenerationRequest(BaseModel):
    category_id: str = Field(default="", max_length=40)
    language: str = Field(default="en", pattern="^en$")
    fields: list[Literal["title", "description"]] = Field(default_factory=lambda: ["title", "description"])


class GeneratedListingContent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    description: str
    brand: str = "Unbranded"


class DraftContentGenerationResponse(BaseModel):
    draft: ProductDraftRead
    title: str
    description: str
    brand: str
    validation: dict[str, object]
    model: str

