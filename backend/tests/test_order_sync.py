from datetime import datetime

from app.services.meli.order_sync import _parse_meli_datetime


def test_parse_meli_datetime_normalizes_offset_to_utc() -> None:
    assert _parse_meli_datetime("2026-08-17T21:03:03.000-04:00") == datetime(
        2026, 8, 18, 1, 3, 3
    )


def test_parse_meli_datetime_accepts_z_suffix() -> None:
    assert _parse_meli_datetime("2026-08-18T01:03:03Z") == datetime(2026, 8, 18, 1, 3, 3)
