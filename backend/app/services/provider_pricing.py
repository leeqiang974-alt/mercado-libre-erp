from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.provider_model_price import ProviderModelPrice
from app.schemas.provider_pricing import ProviderModelPriceCreate, ProviderModelPriceRead
from app.services.audit_events import create_audit_event


@dataclass(frozen=True)
class ReviewCostSnapshot:
    price_config_id: int | None = None
    amount: Decimal | None = None
    currency: str = ""


def save_provider_model_price(
    db: Session, payload: ProviderModelPriceCreate
) -> ProviderModelPrice:
    current = db.scalars(
        select(ProviderModelPrice)
        .where(
            ProviderModelPrice.provider == payload.provider,
            ProviderModelPrice.model == payload.model,
            ProviderModelPrice.active.is_(True),
        )
        .with_for_update()
    ).all()
    next_version = (
        db.scalar(
            select(func.max(ProviderModelPrice.version)).where(
                ProviderModelPrice.provider == payload.provider,
                ProviderModelPrice.model == payload.model,
            )
        )
        or 0
    ) + 1
    if current:
        db.execute(
            update(ProviderModelPrice)
            .where(ProviderModelPrice.id.in_([row.id for row in current]))
            .values(active=False)
        )
    row = ProviderModelPrice(
        provider=payload.provider,
        model=payload.model,
        version=next_version,
        currency=payload.currency,
        input_price_per_million=payload.input_price_per_million,
        output_price_per_million=payload.output_price_per_million,
        active=True,
    )
    db.add(row)
    try:
        db.flush()
        create_audit_event(
            db=db,
            actor_type="operator",
            actor_id="local-ui",
            action="provider_model_price.version_created",
            entity_type="provider_model_price",
            entity_id=str(row.id),
            after={
                "provider": row.provider,
                "model": row.model,
                "version": row.version,
                "currency": row.currency,
                "input_price_per_million": str(row.input_price_per_million),
                "output_price_per_million": str(row.output_price_per_million),
            },
            commit=False,
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Provider model price changed concurrently; reload and retry.",
        ) from exc
    db.refresh(row)
    return row


def deactivate_provider_model_price(db: Session, price_id: int) -> ProviderModelPrice:
    row = db.scalar(
        select(ProviderModelPrice)
        .where(ProviderModelPrice.id == price_id)
        .with_for_update()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Provider model price not found.")
    row.active = False
    create_audit_event(
        db=db,
        actor_type="operator",
        actor_id="local-ui",
        action="provider_model_price.deactivated",
        entity_type="provider_model_price",
        entity_id=str(row.id),
        after={"provider": row.provider, "model": row.model, "version": row.version},
        commit=False,
    )
    db.commit()
    db.refresh(row)
    return row


def list_provider_model_prices(
    db: Session, *, include_history: bool = False
) -> list[ProviderModelPriceRead]:
    statement = select(ProviderModelPrice)
    if not include_history:
        statement = statement.where(ProviderModelPrice.active.is_(True))
    rows = db.scalars(
        statement.order_by(
            ProviderModelPrice.provider, ProviderModelPrice.model, ProviderModelPrice.version.desc()
        )
    ).all()
    return [ProviderModelPriceRead.model_validate(row, from_attributes=True) for row in rows]


def estimate_review_cost(
    db: Session,
    *,
    provider: str,
    model: str,
    input_tokens: int | None,
    output_tokens: int | None,
    price_config_id: int | None = None,
    price_config_captured: bool = False,
) -> ReviewCostSnapshot:
    if provider not in {"claude", "nvidia"} or not model.strip():
        return ReviewCostSnapshot()
    if price_config_captured and price_config_id is None:
        return ReviewCostSnapshot()
    statement = select(ProviderModelPrice).where(
        ProviderModelPrice.provider == provider,
        ProviderModelPrice.model == model,
    )
    if price_config_id is not None:
        statement = statement.where(ProviderModelPrice.id == price_config_id)
    else:
        statement = statement.where(ProviderModelPrice.active.is_(True)).order_by(
            ProviderModelPrice.version.desc()
        )
    price = db.scalar(statement.limit(1))
    if price is None:
        return ReviewCostSnapshot()
    if input_tokens is None or output_tokens is None:
        return ReviewCostSnapshot(
            price_config_id=price.id,
            currency=price.currency,
        )
    amount = (
        Decimal(input_tokens) * price.input_price_per_million
        + Decimal(output_tokens) * price.output_price_per_million
    ) / Decimal(1_000_000)
    return ReviewCostSnapshot(
        price_config_id=price.id,
        amount=amount.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP),
        currency=price.currency,
    )


def active_provider_model_price_id(db: Session, *, provider: str, model: str) -> int | None:
    if provider not in {"claude", "nvidia"} or not model.strip():
        return None
    return db.scalar(
        select(ProviderModelPrice.id)
        .where(
            ProviderModelPrice.provider == provider,
            ProviderModelPrice.model == model,
            ProviderModelPrice.active.is_(True),
        )
        .order_by(ProviderModelPrice.version.desc())
        .limit(1)
    )
