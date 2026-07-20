"""backfill source ASIN on existing product drafts

Revision ID: 20260720_0016
Revises: 20260720_0015
Create Date: 2026-07-20
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260720_0016"
down_revision: str | None = "20260720_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    connection = op.get_bind()
    sources = connection.execute(
        sa.text("SELECT id, asin FROM source_products WHERE asin <> ''")
    ).mappings()
    for source in sources:
        drafts = connection.execute(
            sa.text(
                """
                SELECT id, target_site_id
                FROM product_drafts
                WHERE source_product_id = :source_id AND source_variant_asin = ''
                ORDER BY id
                """
            ),
            {"source_id": source["id"]},
        ).mappings()
        bound_sites: set[str] = set()
        for draft in drafts:
            if draft["target_site_id"] in bound_sites:
                continue
            connection.execute(
                sa.text(
                    "UPDATE product_drafts SET source_variant_asin = :asin WHERE id = :draft_id"
                ),
                {"asin": source["asin"], "draft_id": draft["id"]},
            )
            bound_sites.add(draft["target_site_id"])


def downgrade() -> None:
    # The source ASIN remains valid provenance when rolling the schema back to 0015.
    pass
