"""Bind a continuous Amazon campaign to one browser-extension instance."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260915_0025"
down_revision: str | None = "20260827_0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("keyword_collection_campaigns", sa.Column("bound_worker_id", sa.String(length=120), nullable=True))
    op.add_column("keyword_collection_campaigns", sa.Column("bound_browser_name", sa.String(length=80), nullable=True))
    op.add_column("keyword_collection_campaigns", sa.Column("bound_browser_version", sa.String(length=40), nullable=True))
    op.add_column("keyword_collection_campaigns", sa.Column("bound_extension_version", sa.String(length=40), nullable=True))
    op.add_column("keyword_collection_campaigns", sa.Column("bound_at", sa.DateTime(), nullable=True))
    op.create_index("ix_keyword_collection_campaigns_bound_worker_id", "keyword_collection_campaigns", ["bound_worker_id"])


def downgrade() -> None:
    op.drop_index("ix_keyword_collection_campaigns_bound_worker_id", table_name="keyword_collection_campaigns")
    op.drop_column("keyword_collection_campaigns", "bound_at")
    op.drop_column("keyword_collection_campaigns", "bound_extension_version")
    op.drop_column("keyword_collection_campaigns", "bound_browser_version")
    op.drop_column("keyword_collection_campaigns", "bound_browser_name")
    op.drop_column("keyword_collection_campaigns", "bound_worker_id")
