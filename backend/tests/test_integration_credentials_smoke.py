import pytest

from scripts.integration_credentials_smoke import build_isolated_database_url


def test_smoke_database_url_replaces_production_database():
    database_name = "integration_credentials_smoke_0123456789abcdef0123456789abcdef"

    result = build_isolated_database_url(
        "postgresql+psycopg://meli:secret@127.0.0.1:5432/amazon_meli",
        database_name,
    )

    assert result.endswith(f"/{database_name}")
    assert "/amazon_meli" not in result


@pytest.mark.parametrize(
    "database_name",
    ["amazon_meli", 'integration_credentials_smoke_x";drop database amazon_meli;--'],
)
def test_smoke_database_url_rejects_unsafe_database_names(database_name):
    with pytest.raises(ValueError, match="Unsafe"):
        build_isolated_database_url(
            "postgresql+psycopg://meli:secret@127.0.0.1:5432/amazon_meli",
            database_name,
        )
