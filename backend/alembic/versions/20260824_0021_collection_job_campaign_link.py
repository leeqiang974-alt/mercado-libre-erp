"""link collection jobs to keyword campaigns

Revision ID: 20260824_0021
Revises: 20260824_0020
"""
from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa

revision: str = "20260824_0021"
down_revision: str | None = "20260824_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("collection_jobs", sa.Column("campaign_id", sa.Integer(), nullable=True))
    op.add_column("collection_jobs", sa.Column("campaign_keyword", sa.String(length=240), nullable=True))
    op.create_foreign_key("fk_collection_jobs_campaign_id", "collection_jobs", "keyword_collection_campaigns", ["campaign_id"], ["id"])
    op.create_index("ix_collection_jobs_campaign_id", "collection_jobs", ["campaign_id"])


def downgrade() -> None:
    op.drop_index("ix_collection_jobs_campaign_id", table_name="collection_jobs")
    op.drop_constraint("fk_collection_jobs_campaign_id", "collection_jobs", type_="foreignkey")
    op.drop_column("collection_jobs", "campaign_keyword")
    op.drop_column("collection_jobs", "campaign_id")
