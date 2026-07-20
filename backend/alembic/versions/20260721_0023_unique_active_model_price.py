"""enforce one active price per provider model

Revision ID: 20260721_0023
Revises: 20260721_0022
Create Date: 2026-07-21
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260721_0023"
down_revision: str | None = "20260721_0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "uq_provider_model_prices_active",
        "provider_model_prices",
        ["provider", "model"],
        unique=True,
        postgresql_where=sa.text("active"),
        sqlite_where=sa.text("active"),
    )


def downgrade() -> None:
    op.drop_index("uq_provider_model_prices_active", table_name="provider_model_prices")
