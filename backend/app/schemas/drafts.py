from pydantic import BaseModel, Field


class ProductDraftCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    brand: str = ""
    target_site_id: str = "MLM"
    target_category_id: str = ""
    condition: str = "new"
    price: float | None = None
    currency: str = ""
    stock: int = 0
    listing_type_id: str = ""
    image_urls: list[str] = []
