from pydantic import BaseModel, Field

from app.schemas.drafts import ProductDraftRead


class DraftCategoryUpdate(BaseModel):
    expected_content_version: int = Field(ge=1)
    target_site_id: str = Field(min_length=2, max_length=8)
    category_id: str = Field(min_length=3, max_length=40)


class DraftCategoryRead(BaseModel):
    draft: ProductDraftRead
    category_id: str
    attributes_verified: bool
    attributes: list[dict] = Field(default_factory=list)
