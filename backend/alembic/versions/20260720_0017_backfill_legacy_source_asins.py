"""recover ASIN provenance from legacy Amazon source URLs

Revision ID: 20260720_0017
Revises: 20260720_0016
Create Date: 2026-07-20
"""

from collections.abc import Sequence
import re

from alembic import op
import sqlalchemy as sa

revision: str = "20260720_0017"
down_revision: str | None = "20260720_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ASIN_PATTERN = re.compile(
    r"/(?:dp|gp/product|gp/aw/d)/([A-Z0-9]{10})(?:[/?]|$)",
    re.IGNORECASE,
)


def upgrade() -> None:
    connection = op.get_bind()
    rows = connection.execute(
        sa.text("SELECT id, source_url FROM source_products WHERE asin = ''")
    ).mappings()
    for row in rows:
        match = ASIN_PATTERN.search(row["source_url"] or "")
        if match is None:
            continue
        asin = match.group(1).upper()
        connection.execute(
            sa.text("UPDATE source_products SET asin = :asin WHERE id = :source_id"),
            {"asin": asin, "source_id": row["id"]},
        )
        drafts = connection.execute(
            sa.text(
                """
                SELECT id, target_site_id
                FROM product_drafts
                WHERE source_product_id = :source_id AND source_variant_asin = ''
                ORDER BY id
                """
            ),
            {"source_id": row["id"]},
        ).mappings()
        bound_sites: set[str] = set()
        for draft in drafts:
            if draft["target_site_id"] in bound_sites:
                continue
            connection.execute(
                sa.text(
                    "UPDATE product_drafts SET source_variant_asin = :asin WHERE id = :draft_id"
                ),
                {"asin": asin, "draft_id": draft["id"]},
            )
            bound_sites.add(draft["target_site_id"])


def downgrade() -> None:
    # Recovered provenance is valid data and is intentionally retained.
    pass
