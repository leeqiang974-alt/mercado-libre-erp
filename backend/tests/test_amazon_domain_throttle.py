from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.amazon_domain_throttle import AmazonDomainThrottle
from app.models.registry import import_all_models
from app.services.amazon.throttle import record_domain_outcome, reserve_domain_request


def make_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    import_all_models()
    Base.metadata.create_all(engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def test_domain_request_slot_is_persistent():
    testing_session = make_session()
    now = datetime(2026, 7, 21, 0, 0, tzinfo=UTC)
    with testing_session() as db:
        first = reserve_domain_request(
            db,
            "https://amazon.com/dp/B000TEST01",
            now=now,
            min_interval_seconds=8,
            lease_seconds=60,
        )
        db.commit()
    with testing_session() as db:
        second = reserve_domain_request(
            db,
            "https://www.amazon.com/dp/B000TEST02",
            now=now + timedelta(seconds=1),
            min_interval_seconds=8,
            lease_seconds=60,
        )

    assert first.reserved is True
    assert second.reserved is False
    assert second.domain == "amazon.com"
    assert second.available_at == now + timedelta(seconds=9)


def test_challenge_backoff_grows_and_success_resets_it():
    testing_session = make_session()
    now = datetime(2026, 7, 21, 0, 0, tzinfo=UTC)
    url = "https://amazon.com/dp/B000TEST01"
    with testing_session() as db:
        first = reserve_domain_request(
            db,
            url,
            now=now,
            min_interval_seconds=8,
            lease_seconds=60,
        )
        record_domain_outcome(
            db,
            url,
            outcome="challenge",
            now=now,
            challenge_backoff_base_seconds=300,
            challenge_backoff_max_seconds=900,
            min_interval_seconds=8,
            reservation_id=first.reservation_id,
        )
        db.commit()
    with testing_session() as db:
        second_time = now + timedelta(seconds=301)
        second = reserve_domain_request(
            db,
            url,
            now=second_time,
            min_interval_seconds=8,
            lease_seconds=60,
        )
        record_domain_outcome(
            db,
            url,
            outcome="challenge",
            now=second_time,
            challenge_backoff_base_seconds=300,
            challenge_backoff_max_seconds=900,
            min_interval_seconds=8,
            reservation_id=second.reservation_id,
        )
        db.commit()
        state = db.get(AmazonDomainThrottle, "amazon.com")
        assert state.consecutive_challenges == 2
        assert state.backoff_until.replace(tzinfo=UTC) == now + timedelta(seconds=901)

        success_time = now + timedelta(seconds=902)
        success = reserve_domain_request(
            db,
            url,
            now=success_time,
            min_interval_seconds=8,
            lease_seconds=60,
        )
        record_domain_outcome(
            db,
            url,
            outcome="collected",
            now=success_time,
            challenge_backoff_base_seconds=300,
            challenge_backoff_max_seconds=900,
            min_interval_seconds=8,
            reservation_id=success.reservation_id,
        )
        db.commit()
        db.refresh(state)
        assert state.consecutive_challenges == 0
        assert state.backoff_until is None


def test_stale_outcome_cannot_clear_newer_challenge_backoff():
    testing_session = make_session()
    now = datetime(2026, 7, 21, 0, 0, tzinfo=UTC)
    url = "https://amazon.com/dp/B000TEST01"
    with testing_session() as db:
        stale = reserve_domain_request(
            db,
            url,
            now=now,
            min_interval_seconds=1,
            lease_seconds=1,
        )
        db.commit()
    with testing_session() as db:
        current = reserve_domain_request(
            db,
            url,
            now=now + timedelta(seconds=2),
            min_interval_seconds=1,
            lease_seconds=60,
        )
        assert record_domain_outcome(
            db,
            url,
            outcome="challenge",
            now=now + timedelta(seconds=3),
            challenge_backoff_base_seconds=300,
            challenge_backoff_max_seconds=900,
            min_interval_seconds=1,
            reservation_id=current.reservation_id,
        ) is True
        assert record_domain_outcome(
            db,
            url,
            outcome="collected",
            now=now + timedelta(seconds=4),
            challenge_backoff_base_seconds=300,
            challenge_backoff_max_seconds=900,
            min_interval_seconds=1,
            reservation_id=stale.reservation_id,
        ) is False
        db.commit()
        state = db.get(AmazonDomainThrottle, "amazon.com")
        assert state.consecutive_challenges == 1
        assert state.backoff_until is not None
        assert state.last_outcome == "challenge"

