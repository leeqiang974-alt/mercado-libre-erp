"""add Amazon domain in-flight lease

Revision ID: 20260721_0026
Revises: 20260721_0025
Create Date: 2026-07-21
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260721_0026"
down_revision: str | None = "20260721_0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "amazon_domain_throttles",
        sa.Column("in_flight_until", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "amazon_domain_throttles",
        sa.Column("reservation_id", sa.String(length=36), nullable=True),
    )
    if op.get_bind().dialect.name == "postgresql":
        op.alter_column(
            "collection_jobs",
            "next_attempt_at",
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            postgresql_using="next_attempt_at AT TIME ZONE 'UTC'",
        )
        for column_name in (
            "next_allowed_at",
            "backoff_until",
            "last_request_at",
            "updated_at",
        ):
            op.alter_column(
                "amazon_domain_throttles",
                column_name,
                existing_type=sa.DateTime(),
                type_=sa.DateTime(timezone=True),
                postgresql_using=f"{column_name} AT TIME ZONE 'UTC'",
            )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.alter_column(
            "collection_jobs",
            "next_attempt_at",
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            postgresql_using="next_attempt_at AT TIME ZONE 'UTC'",
        )
        for column_name in (
            "next_allowed_at",
            "backoff_until",
            "last_request_at",
            "updated_at",
        ):
            op.alter_column(
                "amazon_domain_throttles",
                column_name,
                existing_type=sa.DateTime(timezone=True),
                type_=sa.DateTime(),
                postgresql_using=f"{column_name} AT TIME ZONE 'UTC'",
            )
    op.drop_column("amazon_domain_throttles", "reservation_id")
    op.drop_column("amazon_domain_throttles", "in_flight_until")
