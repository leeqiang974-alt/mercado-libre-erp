from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models.product_draft import ProductDraft
from app.schemas.drafts import ProductDraftCreate, ProductDraftRead


def update_draft_content(
    db: Session,
    product_draft_id: int,
    **values: object,
) -> None:
    """Update draft fields and invalidate review with an atomic version increment."""
    # Sessions disable autoflush; preserve pending config changes before direct SQL.
    db.flush()
    result = db.execute(
        update(ProductDraft)
        .where(ProductDraft.id == product_draft_id)
        .values(
            **values,
            content_version=ProductDraft.content_version + 1,
            risk_status="unreviewed",
        )
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        raise LookupError("Product draft not found.")


def create_product_draft(
    db: Session, draft: ProductDraftCreate, source_product_id: int | None = None
) -> ProductDraft:
    model = ProductDraft(
        source_product_id=source_product_id,
        target_site_id=draft.target_site_id,
        target_category_id=draft.target_category_id,
        title=draft.title,
        description=draft.description,
        brand=draft.brand,
        condition=draft.condition,
        source_price=draft.source_price if draft.source_price is not None else draft.price,
        source_currency=draft.source_currency or draft.currency,
        price=draft.price,
        currency=draft.currency,
        stock=draft.stock,
        listing_type_id=draft.listing_type_id,
        image_urls_json=draft.image_urls,
    )
    db.add(model)
    db.commit()
    db.refresh(model)
    return model


def to_draft_read(model: ProductDraft) -> ProductDraftRead:
    return ProductDraftRead(
        id=model.id,
        title=model.title,
        description=model.description,
        brand=model.brand,
        target_site_id=model.target_site_id,
        target_category_id=model.target_category_id,
        condition=model.condition,
        source_price=model.source_price,
        source_currency=model.source_currency,
        price=model.price,
        currency=model.currency,
        stock=model.stock,
        listing_type_id=model.listing_type_id,
        image_urls=model.image_urls_json or [],
        status=model.status.value if hasattr(model.status, "value") else str(model.status),
        risk_status=model.risk_status,
    )


def list_product_drafts(db: Session) -> list[ProductDraftRead]:
    return [to_draft_read(model) for model in db.query(ProductDraft).order_by(ProductDraft.id.desc()).all()]
