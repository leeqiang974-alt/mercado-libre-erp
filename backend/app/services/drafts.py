import re

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.product_draft import ProductDraft
from app.schemas.drafts import UNBRANDED, ProductDraftContentUpdate, ProductDraftCreate, ProductDraftRead
from app.services.audit_events import create_audit_event
from app.services.amazon.media import prepare_listing_title, select_listing_images, select_product_video_urls


_BRAND_LABEL_PATTERN = re.compile(r"^\s*(?:brand|brand name|marca)\s*[:\-].*$", re.IGNORECASE)


def sanitize_unbranded_description(description: str, source_brand: str = "") -> str:
    """Remove marketplace brand fields from copy while retaining source evidence separately."""
    clean_lines = [line for line in description.strip().splitlines() if not _BRAND_LABEL_PATTERN.match(line)]
    cleaned = "\n".join(clean_lines)
    brand = source_brand.strip()
    if brand:
        cleaned = re.sub(
            rf"(?<![A-Za-z0-9]){re.escape(brand)}(?![A-Za-z0-9])",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


def normalize_listing_title(title: str, source_brand: str = "") -> str:
    normalized = " ".join(title.split())
    if len(normalized) > 60:
        raise HTTPException(status_code=422, detail="title must be 60 characters or fewer")
    if source_brand.strip() and source_brand.casefold() in normalized.casefold():
        raise HTTPException(status_code=422, detail="title must not contain the source brand")
    return normalized


def update_draft_content(
    db: Session,
    product_draft_id: int,
    expected_content_version: int | None = None,
    **values: object,
) -> None:
    """Update draft fields and invalidate review with an atomic version increment."""
    # Sessions disable autoflush; preserve pending config changes before direct SQL.
    db.flush()
    statement = update(ProductDraft).where(ProductDraft.id == product_draft_id)
    if expected_content_version is not None:
        statement = statement.where(ProductDraft.content_version == expected_content_version)
    result = db.execute(
        statement
        .values(
            **values,
            content_version=ProductDraft.content_version + 1,
            risk_status="unreviewed",
        )
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        if expected_content_version is not None and db.get(ProductDraft, product_draft_id) is not None:
            raise HTTPException(status_code=409, detail="draft_content_version_conflict")
        raise LookupError("Product draft not found.")


def save_product_draft_content(
    db: Session,
    product_draft_id: int,
    payload: ProductDraftContentUpdate,
) -> ProductDraft:
    draft = db.scalar(
        select(ProductDraft).where(ProductDraft.id == product_draft_id).with_for_update()
    )
    if draft is None:
        raise HTTPException(status_code=404, detail="Product draft not found.")
    if draft.content_version != payload.expected_content_version:
        raise HTTPException(status_code=409, detail="draft_content_version_conflict")

    source_brand = ""
    if draft.source_product_id:
        from app.models.source_product import SourceProduct

        source = db.get(SourceProduct, draft.source_product_id)
        source_brand = source.brand if source else ""
    normalized_title = normalize_listing_title(prepare_listing_title(payload.title, source_brand), source_brand)
    normalized_description = sanitize_unbranded_description(payload.description, source_brand)
    values = {
        "title": normalized_title,
        "description": normalized_description,
        "brand": UNBRANDED,
        "image_urls_json": select_listing_images(payload.image_urls),
        "video_urls_json": select_product_video_urls(payload.video_urls),
    }
    before_values = {
        "title": draft.title,
        "description": draft.description,
        "brand": draft.brand,
        "image_urls_json": draft.image_urls_json or [],
        "video_urls_json": draft.video_urls_json or [],
    }
    changed_fields = [name for name, value in values.items() if before_values[name] != value]
    if not changed_fields:
        return draft

    previous_version = draft.content_version
    update_draft_content(
        db,
        product_draft_id,
        expected_content_version=previous_version,
        **values,
    )
    create_audit_event(
        db,
        actor_type="human",
        actor_id="operator",
        action="draft.content_updated",
        entity_type="product_draft",
        entity_id=str(product_draft_id),
        before={
            "content_version": previous_version,
            "title": draft.title,
            "brand": draft.brand,
            "description_length": len(draft.description),
            "image_count": len(draft.image_urls_json or []),
            "video_count": len(draft.video_urls_json or []),
        },
        after={
            "content_version": previous_version + 1,
            "changed_fields": changed_fields,
            "title": payload.title,
            "brand": payload.brand,
            "description_length": len(normalized_description),
            "image_count": len(payload.image_urls),
            "video_count": len(payload.video_urls),
        },
        commit=False,
    )
    db.commit()
    db.refresh(draft)
    return draft


def create_product_draft(
    db: Session,
    draft: ProductDraftCreate,
    source_product_id: int | None = None,
    source_variant_asin: str = "",
    source_variant_attributes: dict[str, str] | None = None,
    commit: bool = True,
) -> ProductDraft:
    model = ProductDraft(
        source_product_id=source_product_id,
        source_variant_asin=source_variant_asin,
        source_variant_attributes_json=source_variant_attributes or {},
        target_site_id=draft.target_site_id,
        target_category_id=draft.target_category_id,
        title=draft.title,
        description=sanitize_unbranded_description(draft.description, draft.brand),
        brand=UNBRANDED,
        condition=draft.condition,
        source_price=draft.source_price,
        source_currency=draft.source_currency,
        price=draft.price,
        currency=draft.currency,
        stock=draft.stock,
        listing_type_id=draft.listing_type_id,
        image_urls_json=select_listing_images(draft.image_urls),
        video_urls_json=select_product_video_urls(draft.video_urls),
    )
    db.add(model)
    if commit:
        db.commit()
        db.refresh(model)
    else:
        db.flush()
    return model


def to_draft_read(model: ProductDraft) -> ProductDraftRead:
    return ProductDraftRead(
        id=model.id,
        source_product_id=model.source_product_id,
        source_variant_asin=model.source_variant_asin,
        source_variant_attributes=model.source_variant_attributes_json or {},
        title=model.title,
        description=model.description,
        brand=UNBRANDED,
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
        video_urls=model.video_urls_json or [],
        status=model.status.value if hasattr(model.status, "value") else str(model.status),
        risk_status=model.risk_status,
        content_version=model.content_version,
    )


def list_product_drafts(
    db: Session, *, limit: int = 1000, compact: bool = False
) -> list[ProductDraftRead]:
    """Return the requested newest drafts without breaking the list endpoint.

    ``compact`` is accepted as part of the listing-rail API contract.  The
    read schema currently includes the same persisted fields in both modes,
    so it cannot safely omit columns yet; keeping the argument here prevents
    the public list route from raising a TypeError while the UI paginates.
    """
    del compact
    models = (
        db.query(ProductDraft)
        .order_by(ProductDraft.id.desc())
        .limit(max(1, min(int(limit), 1000)))
        .all()
    )
    return [to_draft_read(model) for model in models]
