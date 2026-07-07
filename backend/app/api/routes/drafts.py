from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.drafts import ProductDraftRead
from app.services.drafts import list_product_drafts

router = APIRouter(prefix="/api/drafts", tags=["drafts"])


@router.get("", response_model=list[ProductDraftRead])
def list_drafts(db: Session = Depends(get_db)) -> list[ProductDraftRead]:
    return list_product_drafts(db)
