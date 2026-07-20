from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.amazon_domain_throttle import AmazonDomainThrottle
from app.services.amazon.collector import amazon_marketplace_domain


@dataclass(frozen=True)
class DomainReservation:
    domain: str | None
    reserved: bool
    available_at: datetime | None = None
    reservation_id: str | None = None


def reserve_domain_request(
    db: Session,
    source_url: str,
    *,
    now: datetime,
    min_interval_seconds: int,
    lease_seconds: int,
) -> DomainReservation:
    domain = amazon_marketplace_domain(source_url)
    if domain is None:
        return DomainReservation(domain=None, reserved=True)

    _lock_domain(db, domain)
    state = _locked_state(db, domain)
    available_at = _next_check_at(
        state,
        now=now,
        min_interval_seconds=min_interval_seconds,
    )
    if available_at is not None and _utc(available_at) > _utc(now):
        return DomainReservation(
            domain=domain,
            reserved=False,
            available_at=_utc(available_at),
        )

    state.last_request_at = now
    state.next_allowed_at = now + timedelta(seconds=min_interval_seconds)
    state.in_flight_until = now + timedelta(seconds=lease_seconds)
    state.reservation_id = str(uuid4())
    state.last_outcome = "running"
    db.flush()
    return DomainReservation(
        domain=domain,
        reserved=True,
        reservation_id=state.reservation_id,
    )


def record_domain_outcome(
    db: Session,
    source_url: str,
    *,
    outcome: str,
    now: datetime,
    challenge_backoff_base_seconds: int,
    challenge_backoff_max_seconds: int,
    min_interval_seconds: int,
    reservation_id: str,
) -> bool:
    domain = amazon_marketplace_domain(source_url)
    if domain is None:
        return False
    _lock_domain(db, domain)
    state = _locked_state(db, domain)
    if state.reservation_id != reservation_id:
        return False
    state.last_outcome = outcome
    state.in_flight_until = None
    state.reservation_id = None
    state.next_allowed_at = now + timedelta(seconds=min_interval_seconds)
    if outcome == "challenge":
        state.consecutive_challenges += 1
        delay = _backoff_seconds(
            challenge_backoff_base_seconds,
            challenge_backoff_max_seconds,
            state.consecutive_challenges,
        )
        state.backoff_until = now + timedelta(seconds=delay)
    elif outcome == "collected":
        state.consecutive_challenges = 0
        state.backoff_until = None
    db.flush()
    return True


def _lock_domain(db: Session, domain: str) -> None:
    if db.get_bind().dialect.name == "postgresql":
        db.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:lock_name))"),
            {"lock_name": f"amazon_domain:{domain}"},
        )


def _locked_state(db: Session, domain: str) -> AmazonDomainThrottle:
    state = (
        db.query(AmazonDomainThrottle)
        .filter(AmazonDomainThrottle.domain == domain)
        .with_for_update()
        .populate_existing()
        .one_or_none()
    )
    if state is None:
        state = AmazonDomainThrottle(domain=domain)
        db.add(state)
        db.flush()
    return state


def _latest(*values: datetime | None) -> datetime | None:
    present = [_utc(value) for value in values if value is not None]
    return max(present) if present else None


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _backoff_seconds(base: int, maximum: int, challenge_count: int) -> int:
    delay = base
    for _ in range(max(0, challenge_count - 1)):
        delay = min(delay * 2, maximum)
        if delay == maximum:
            break
    return delay


def _next_check_at(
    state: AmazonDomainThrottle,
    *,
    now: datetime,
    min_interval_seconds: int,
) -> datetime | None:
    current = _utc(now)
    ordinary_block = _latest(state.next_allowed_at, state.backoff_until)
    in_flight_until = (
        _utc(state.in_flight_until) if state.in_flight_until is not None else None
    )
    if in_flight_until is not None and in_flight_until > current:
        lease_probe = min(
            in_flight_until,
            current + timedelta(seconds=min_interval_seconds),
        )
        return _latest(ordinary_block, lease_probe)
    return ordinary_block
