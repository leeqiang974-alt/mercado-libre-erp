from sqlalchemy.orm import Session

from app.models.draft_pricing_config import DraftPricingConfig
from app.models.product_draft import ProductDraft
from app.services.meli.sites import expected_currency


def add_current_pricing(db: Session, draft: ProductDraft) -> DraftPricingConfig:
    """Seed neutral saved pricing without changing the draft content version."""
    if draft.id is None or draft.price is None or draft.price <= 0:
        raise ValueError("A persisted draft with a positive target price is required.")
    target_currency = expected_currency(draft.target_site_id)
    if not target_currency or draft.currency.strip().upper() != target_currency:
        raise ValueError("Draft currency must match its Mercado Libre site.")
    if draft.source_price is None:
        draft.source_price = draft.price
        draft.source_currency = target_currency
    elif not draft.source_currency.strip():
        draft.source_currency = target_currency

    config = DraftPricingConfig(
        product_draft_id=draft.id,
        source_price=draft.source_price,
        source_currency=draft.source_currency.strip().upper(),
        target_currency=target_currency,
        exchange_rate=1,
        purchase_extra_cost=0,
        shipping_cost=0,
        platform_fee_rate=0,
        tax_rate=0,
        profit_margin_rate=0,
        rounding_increment=0.01,
        landed_cost=draft.price,
        target_price=draft.price,
    )
    db.add(config)
    return config
