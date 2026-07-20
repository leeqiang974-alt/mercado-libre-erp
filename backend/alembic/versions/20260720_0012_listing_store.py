"""bind listing delivery selection to an authorized store

Revision ID: 20260720_0012
Revises: 20260720_0011
Create Date: 2026-07-20
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260720_0012"
down_revision: str | None = "20260720_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("draft_listing_configs") as batch_op:
        batch_op.add_column(sa.Column("store_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_draft_listing_configs_store_id",
            "stores",
            ["store_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("draft_listing_configs") as batch_op:
        batch_op.drop_constraint(
            "fk_draft_listing_configs_store_id",
            type_="foreignkey",
        )
        batch_op.drop_column("store_id")
