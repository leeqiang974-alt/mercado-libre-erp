"""add keyword collection campaigns

Revision ID: 20260824_0020
Revises: 20260720_0019
"""
from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa

revision: str = "20260824_0020"
down_revision: str | None = "20260819_0035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade() -> None:
    op.create_table(
        "keyword_collection_campaigns",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("domain", sa.String(length=120), nullable=False, server_default="amazon.com"),
        sa.Column("target_site_id", sa.String(length=8), nullable=False, server_default="CBT"),
        sa.Column("keywords_json", sa.JSON(), nullable=False),
        sa.Column("pages_per_keyword", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("current_keyword_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("current_page", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("discovered_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("queued_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duplicate_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("message", sa.Text(), nullable=False, server_default="等待开始"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

def downgrade() -> None:
    op.drop_table("keyword_collection_campaigns")
