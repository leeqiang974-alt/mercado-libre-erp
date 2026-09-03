from datetime import UTC, datetime

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.source_product import SourceProduct, SourceProductStatus
from app.models.product_draft import ProductDraft
from app.schemas.source_products import (
    AmazonSourceSnapshot,
    SourceProductRead,
    SourceProductSummaryRead,
)
from app.services.amazon.parser import extract_amazon_asin
from app.services.amazon.media import merge_listing_images, select_listing_images
from app.services.amazon.normalizer import normalize_amazon_product
from app.services.drafts import create_product_draft

EXACT_PAGE_EVIDENCE_STATUSES = {
    SourceProductStatus.COLLECTED,
    SourceProductStatus.NEEDS_MANUAL_ACTION,
}


def create_source_product(
    db: Session,
    source_url: str,
    status: SourceProductStatus,
    collection_error: str = "",
    snapshot: AmazonSourceSnapshot | dict | None = None,
    collection_method: str = "browser_page",
) -> SourceProduct:
    normalized_snapshot = (
        snapshot
        if isinstance(snapshot, AmazonSourceSnapshot)
        else AmazonSourceSnapshot.model_validate(snapshot)
        if snapshot is not None
        else None
    )
    model = SourceProduct(
        source_url=source_url,
        asin=extract_amazon_asin(source_url) or "",
        collection_method=collection_method,
        raw_status=status,
        collected_at=datetime.now(UTC) if status == SourceProductStatus.COLLECTED else None,
        collection_error=collection_error,
        title=normalized_snapshot.title if normalized_snapshot else "",
        brand=normalized_snapshot.brand if normalized_snapshot else "",
        source_price=normalized_snapshot.price.amount if normalized_snapshot else None,
        source_currency=normalized_snapshot.price.currency if normalized_snapshot else "",
        description=normalized_snapshot.description if normalized_snapshot else "",
        bullets_json=normalized_snapshot.bullets if normalized_snapshot else [],
        image_urls_json=(
            select_listing_images(normalized_snapshot.images)
            if normalized_snapshot
            else []
        ),
        variants_json=(
            [
                {
                    **variant.model_dump(),
                    "image_urls": select_listing_images(variant.image_urls),
                }
                for variant in normalized_snapshot.variants
            ]
            if normalized_snapshot
            else []
        ),
        technical_details_json=(
            normalized_snapshot.technical_details if normalized_snapshot else {}
        ),
        measurements_json=(
            normalized_snapshot.measurements.model_dump(exclude_none=True)
            if normalized_snapshot
            else {}
        ),
    )
    db.add(model)
    db.flush()
    return model


def to_source_product_read(model: SourceProduct) -> SourceProductRead:
    snapshot = None
    if model.title or model.image_urls_json or model.variants_json:
        snapshot = AmazonSourceSnapshot(
            source_url=model.source_url,
            title=model.title,
            price={"amount": model.source_price, "currency": model.source_currency},
            brand=model.brand,
            bullets=model.bullets_json or [],
            description=model.description,
            images=model.image_urls_json or [],
            variants=model.variants_json or [],
            technical_details=model.technical_details_json or {},
            measurements=model.measurements_json or {},
        )
    return SourceProductRead(
        id=model.id,
        source=model.source,
        source_url=model.source_url,
        asin=model.asin,
        status=model.raw_status.value,
        collection_method=model.collection_method,
        collected_at=model.collected_at,
        collection_error=model.collection_error,
        snapshot=snapshot,
    )


def to_source_product_summary(model: SourceProduct) -> SourceProductSummaryRead:
    images = model.image_urls_json or []
    has_snapshot = bool(model.title or images or model.variants_json)
    return SourceProductSummaryRead(
        id=model.id,
        asin=model.asin,
        status=model.raw_status.value,
        collection_method=model.collection_method,
        title=model.title,
        brand=model.brand,
        source_price=model.source_price,
        source_currency=model.source_currency,
        primary_image_url=images[0] if images else "",
        image_count=len(images),
        variant_count=len(model.variants_json or []),
        has_snapshot=has_snapshot,
        collection_error=model.collection_error,
    )


def selected_source_variant(
    snapshot: AmazonSourceSnapshot | dict | None,
    fallback_asin: str,
) -> tuple[str, dict[str, str]]:
    normalized = (
        snapshot
        if isinstance(snapshot, AmazonSourceSnapshot)
        else AmazonSourceSnapshot.model_validate(snapshot)
        if snapshot is not None
        else None
    )
    if normalized is not None:
        selected = next((variant for variant in normalized.variants if variant.selected), None)
        if selected is not None:
            return selected.asin, selected.attributes
    return fallback_asin, {}


def create_or_get_source_variant_draft(
    db: Session,
    source: SourceProduct,
    variant_asin: str,
    target_site_id: str,
) -> tuple[ProductDraft, bool]:
    normalized_asin = variant_asin.strip().upper()
    source_id = source.id
    source_read = to_source_product_read(source)
    snapshot = source_read.snapshot
    if snapshot is None:
        raise ValueError("source_snapshot_unavailable")
    variant = next(
        (item for item in snapshot.variants if item.asin == normalized_asin),
        None,
    )
    if variant is None:
        raise LookupError("source_variant_not_found")

    selected_asin, _ = selected_source_variant(snapshot, source.asin)
    if variant.asin != selected_asin:
        raise ValueError("variant_page_collection_required")

    existing = (
        db.query(ProductDraft)
        .filter(
            ProductDraft.source_product_id == source.id,
            ProductDraft.source_variant_asin == normalized_asin,
            ProductDraft.target_site_id == target_site_id,
        )
        .one_or_none()
    )
    if existing is not None:
        return existing, False

    draft_snapshot = snapshot.model_dump()
    # Keep the selected variant image first, but retain the shared gallery too.
    # Amazon often exposes only one color image in the variant block while the
    # remaining product images live in the common gallery.
    draft_snapshot["images"] = merge_listing_images(variant.image_urls, snapshot.images)
    draft = normalize_amazon_product(draft_snapshot, target_site_id)
    if variant.attributes:
        variant_lines = "\n".join(
            f"{name}: {value}" for name, value in variant.attributes.items()
        )
        draft.description = "\n\n".join(
            part for part in [draft.description, f"Amazon variant:\n{variant_lines}"] if part
        )
    try:
        model = create_product_draft(
            db,
            draft,
            source_product_id=source.id,
            source_variant_asin=variant.asin,
            source_variant_attributes=variant.attributes,
            commit=False,
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        winner = (
            db.query(ProductDraft)
            .filter(
                ProductDraft.source_product_id == source_id,
                ProductDraft.source_variant_asin == normalized_asin,
                ProductDraft.target_site_id == target_site_id,
            )
            .one_or_none()
        )
        if winner is None:
            raise exc
        return winner, False
    db.refresh(model)
    return model, True


def source_variant_evidence_error(
    db: Session, draft: ProductDraft
) -> str | None:
    variant_asin = (draft.source_variant_asin or "").strip().upper()
    if draft.source_product_id is None or not variant_asin:
        return None
    source = db.get(SourceProduct, draft.source_product_id)
    if (
        source is not None
        and source.raw_status in EXACT_PAGE_EVIDENCE_STATUSES
        and source.asin.strip().upper() == variant_asin
    ):
        return None
    return "variant_page_collection_required"
