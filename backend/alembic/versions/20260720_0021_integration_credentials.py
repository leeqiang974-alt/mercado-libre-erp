"""add encrypted integration credentials

Revision ID: 20260720_0021
Revises: 20260720_0020
Create Date: 2026-07-20
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260720_0021"
down_revision: str | None = "20260720_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "integration_credentials",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("credential_key", sa.String(length=80), nullable=False),
        sa.Column("encrypted_value", sa.Text(), nullable=False),
        sa.Column("last_operation_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_integration_credentials_credential_key"),
        "integration_credentials",
        ["credential_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_integration_credentials_credential_key"),
        table_name="integration_credentials",
    )
    op.drop_table("integration_credentials")
