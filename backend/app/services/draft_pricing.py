from datetime import UTC, datetime
from decimal import Decimal, ROUND_CEILING

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.draft_pricing_config import DraftPricingConfig
from app.models.product_draft import ProductDraft
from app.schemas.pricing import DraftPricingRead, DraftPricingUpsert
from app.services.audit_events import create_audit_event


def calculate_target_price(payload: DraftPricingUpsert) -> tuple[float, float]:
    source = Decimal(str(payload.source_price))
    exchange = Decimal(str(payload.exchange_rate))
    extra = Decimal(str(payload.purchase_extra_cost))
    shipping = Decimal(str(payload.shipping_cost))
    landed = source * exchange + extra + shipping
    rate_total = (
        Decimal(str(payload.platform_fee_rate))
        + Decimal(str(payload.tax_rate))
        + Decimal(str(payload.profit_margin_rate))
    )
    raw_price = landed / (Decimal("1") - rate_total)
    increment = Decimal(str(payload.rounding_increment))
    rounded = (raw_price / increment).to_integral_value(rounding=ROUND_CEILING) * increment
    return float(landed.quantize(Decimal("0.01"))), float(rounded)


def upsert_draft_pricing(
    db: Session, product_draft_id: int, payload: DraftPricingUpsert
) -> DraftPricingConfig:
    draft = db.get(ProductDraft, product_draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Product draft not found.")
    before = {
        "price": draft.price,
        "currency": draft.currency,
        "source_price": draft.source_price,
        "source_currency": draft.source_currency,
    }
    landed_cost, target_price = calculate_target_price(payload)
    config = (
        db.query(DraftPricingConfig)
        .filter(DraftPricingConfig.product_draft_id == product_draft_id)
        .one_or_none()
    )
    if config is None:
        config = DraftPricingConfig(product_draft_id=product_draft_id)
        db.add(config)
    for name, value in payload.model_dump().items():
        setattr(config, name, value)
    config.landed_cost = landed_cost
    config.target_price = target_price
    config.updated_at = datetime.now(UTC)
    draft.source_price = payload.source_price
    draft.source_currency = payload.source_currency
    draft.price = target_price
    draft.currency = payload.target_currency
    draft.content_version += 1
    draft.risk_status = "unreviewed"
    db.commit()
    db.refresh(config)
    create_audit_event(
        db,
        actor_type="human",
        actor_id="operator",
        action="draft_pricing_updated",
        entity_type="product_draft",
        entity_id=str(product_draft_id),
        before=before,
        after={
            "landed_cost": landed_cost,
            "price": target_price,
            "currency": payload.target_currency,
            "formula": payload.model_dump(),
        },
    )
    return config


def get_draft_pricing(db: Session, product_draft_id: int) -> DraftPricingConfig:
    config = (
        db.query(DraftPricingConfig)
        .filter(DraftPricingConfig.product_draft_id == product_draft_id)
        .one_or_none()
    )
    if config is None:
        raise HTTPException(status_code=404, detail="Pricing config not found.")
    return config


def to_pricing_read(config: DraftPricingConfig) -> DraftPricingRead:
    return DraftPricingRead(
        id=config.id,
        product_draft_id=config.product_draft_id,
        source_price=config.source_price,
        source_currency=config.source_currency,
        target_currency=config.target_currency,
        exchange_rate=config.exchange_rate,
        purchase_extra_cost=config.purchase_extra_cost,
        shipping_cost=config.shipping_cost,
        platform_fee_rate=config.platform_fee_rate,
        tax_rate=config.tax_rate,
        profit_margin_rate=config.profit_margin_rate,
        rounding_increment=config.rounding_increment,
        landed_cost=config.landed_cost,
        target_price=config.target_price,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )
