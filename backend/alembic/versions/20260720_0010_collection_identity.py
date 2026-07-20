"""index normalized Amazon collection identities

Revision ID: 20260720_0010
Revises: 20260720_0009
Create Date: 2026-07-20
"""

from collections.abc import Sequence
import re
from urllib.parse import urlparse

from alembic import op
import sqlalchemy as sa

revision: str = "20260720_0010"
down_revision: str | None = "20260720_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AMAZON_DOMAINS = (
    "amazon.com", "amazon.ca", "amazon.com.mx", "amazon.com.br",
    "amazon.co.uk", "amazon.de", "amazon.fr", "amazon.it", "amazon.es",
    "amazon.nl", "amazon.se", "amazon.pl", "amazon.com.be", "amazon.ie",
    "amazon.co.jp", "amazon.in", "amazon.com.au", "amazon.sg", "amazon.ae",
    "amazon.sa", "amazon.com.tr",
)
ASIN_PATTERN = re.compile(
    r"/(?:dp|gp/product|gp/aw/d)/([A-Za-z0-9]{10})(?:[/?#]|$)",
    re.IGNORECASE,
)


def _identity(source_url: str) -> str | None:
    try:
        parsed = urlparse(source_url.strip())
    except ValueError:
        return None
    host = (parsed.hostname or "").lower().rstrip(".")
    domain = next(
        (candidate for candidate in sorted(AMAZON_DOMAINS, key=len, reverse=True)
         if host == candidate or host.endswith(f".{candidate}")),
        None,
    )
    match = ASIN_PATTERN.search(parsed.path)
    if domain is None or match is None:
        return None
    return f"https://{domain}/dp/{match.group(1).upper()}"


def upgrade() -> None:
    op.add_column(
        "collection_jobs",
        sa.Column("source_identity", sa.String(length=256), nullable=True),
    )
    connection = op.get_bind()
    jobs = sa.table(
        "collection_jobs",
        sa.column("id", sa.Integer()),
        sa.column("source_url", sa.Text()),
        sa.column("source_identity", sa.String(length=256)),
        sa.column("target_site_id", sa.String(length=8)),
    )
    rows = list(
        connection.execute(
            sa.select(jobs.c.id, jobs.c.source_url, jobs.c.target_site_id)
        ).mappings()
    )
    for row in rows:
        connection.execute(
            jobs.update().where(jobs.c.id == row["id"]).values(
                source_identity=_identity(row["source_url"]),
                target_site_id=row["target_site_id"].strip().upper(),
            )
        )
    op.create_index(
        "ix_collection_jobs_site_identity",
        "collection_jobs",
        ["target_site_id", "source_identity"],
    )


def downgrade() -> None:
    op.drop_index("ix_collection_jobs_site_identity", table_name="collection_jobs")
    op.drop_column("collection_jobs", "source_identity")
