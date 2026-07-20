from datetime import UTC, datetime
from decimal import Decimal, ROUND_CEILING
from math import isclose

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.draft_pricing_config import DraftPricingConfig
from app.models.product_draft import ProductDraft
from app.schemas.pricing import DraftPricingRead, DraftPricingUpsert
from app.services.audit_events import create_audit_event
from app.services.drafts import update_draft_content
from app.services.meli.sites import expected_currency


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
    draft = db.scalar(
        select(ProductDraft).where(ProductDraft.id == product_draft_id).with_for_update()
    )
    if draft is None:
        raise HTTPException(status_code=404, detail="Product draft not found.")
    evidence_errors = _pricing_input_evidence_errors(draft, payload)
    if evidence_errors:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_pricing_evidence", "errors": evidence_errors},
        )
    before = {
        "price": draft.price,
        "currency": draft.currency,
        "source_price": draft.source_price,
        "source_currency": draft.source_currency,
    }
    config = (
        db.query(DraftPricingConfig)
        .filter(DraftPricingConfig.product_draft_id == product_draft_id)
        .one_or_none()
    )
    if config is None:
        config = DraftPricingConfig(product_draft_id=product_draft_id)
        db.add(config)
    effective_formula = payload.model_dump()
    effective_formula["source_price"] = draft.source_price
    effective_formula["source_currency"] = draft.source_currency.strip().upper()
    effective_formula["target_currency"] = expected_currency(draft.target_site_id)
    effective_payload = DraftPricingUpsert(**effective_formula)
    landed_cost, target_price = calculate_target_price(effective_payload)
    for name, value in effective_formula.items():
        setattr(config, name, value)
    config.landed_cost = landed_cost
    config.target_price = target_price
    config.updated_at = datetime.now(UTC)
    update_draft_content(
        db,
        product_draft_id,
        price=target_price,
        currency=effective_formula["target_currency"],
    )
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
            "currency": effective_formula["target_currency"],
            "formula": effective_formula,
        },
    )
    return config


def draft_pricing_errors(db: Session, draft: ProductDraft) -> list[str]:
    config = (
        db.query(DraftPricingConfig)
        .populate_existing()
        .filter(DraftPricingConfig.product_draft_id == draft.id)
        .one_or_none()
    )
    if config is None:
        return ["saved_pricing_required"]
    errors: list[str] = []
    if draft.source_price is None or draft.source_price <= 0 or not draft.source_currency.strip():
        errors.append("source_price_evidence_required")
    else:
        if Decimal(str(config.source_price)) != Decimal(str(draft.source_price)):
            errors.append("pricing_source_price_mismatch")
        if config.source_currency.strip().upper() != draft.source_currency.strip().upper():
            errors.append("pricing_source_currency_mismatch")
    site_currency = expected_currency(draft.target_site_id)
    if not site_currency or config.target_currency.strip().upper() != site_currency:
        errors.append("pricing_target_currency_mismatch")
    if draft.currency.strip().upper() != config.target_currency.strip().upper():
        errors.append("draft_currency_not_from_saved_pricing")
    if draft.price is None or not isclose(
        draft.price, config.target_price, rel_tol=0, abs_tol=1e-9
    ):
        errors.append("draft_price_not_from_saved_pricing")
    try:
        calculated_landed, calculated_target = calculate_target_price(
            DraftPricingUpsert(
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
            )
        )
    except ValueError:
        errors.append("saved_pricing_formula_invalid")
    else:
        if not isclose(config.landed_cost, calculated_landed, rel_tol=0, abs_tol=1e-9):
            errors.append("saved_landed_cost_mismatch")
        if not isclose(config.target_price, calculated_target, rel_tol=0, abs_tol=1e-9):
            errors.append("saved_target_price_mismatch")
    return list(dict.fromkeys(errors))


def require_current_draft_pricing(db: Session, draft: ProductDraft) -> DraftPricingConfig:
    errors = draft_pricing_errors(db, draft)
    if errors:
        raise HTTPException(
            status_code=409,
            detail={"code": "draft_pricing_not_ready", "errors": errors},
        )
    return get_draft_pricing(db, draft.id)


def _pricing_input_evidence_errors(
    draft: ProductDraft, payload: DraftPricingUpsert
) -> list[str]:
    errors: list[str] = []
    if draft.source_price is None or draft.source_price <= 0 or not draft.source_currency.strip():
        errors.append("source_price_evidence_required")
    else:
        if Decimal(str(payload.source_price)) != Decimal(str(draft.source_price)):
            errors.append("source_price_is_read_only")
        if payload.source_currency != draft.source_currency.strip().upper():
            errors.append("source_currency_is_read_only")
    site_currency = expected_currency(draft.target_site_id)
    if not site_currency or payload.target_currency != site_currency:
        errors.append("target_currency_mismatch")
    return errors


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
