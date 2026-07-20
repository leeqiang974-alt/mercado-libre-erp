"""allow unclassified legacy drafts beside unique source variants

Revision ID: 20260720_0018
Revises: 20260720_0017
Create Date: 2026-07-20
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260720_0018"
down_revision: str | None = "20260720_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

IDENTITY_NAME = "uq_product_drafts_source_variant_site"


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    constraints = {
        item["name"] for item in inspector.get_unique_constraints("product_drafts")
    }
    if IDENTITY_NAME in constraints:
        with op.batch_alter_table("product_drafts") as batch_op:
            batch_op.drop_constraint(IDENTITY_NAME, type_="unique")

    indexes = {item["name"] for item in sa.inspect(connection).get_indexes("product_drafts")}
    if IDENTITY_NAME not in indexes:
        op.create_index(
            IDENTITY_NAME,
            "product_drafts",
            ["source_product_id", "source_variant_asin", "target_site_id"],
            unique=True,
            postgresql_where=sa.text("source_variant_asin <> ''"),
            sqlite_where=sa.text("source_variant_asin <> ''"),
        )


def downgrade() -> None:
    # Keep the corrected partial index; restoring the old constraint could reject legacy data.
    pass
