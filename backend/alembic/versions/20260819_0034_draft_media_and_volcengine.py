"""add draft video media and Volcengine credential support

Revision ID: 20260819_0034
Revises: 20260819_0033
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260819_0034"
down_revision: str | None = "20260819_0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("product_drafts") as batch_op:
        batch_op.add_column(sa.Column("video_urls_json", sa.JSON(), nullable=False, server_default="[]"))


def downgrade() -> None:
    with op.batch_alter_table("product_drafts") as batch_op:
        batch_op.drop_column("video_urls_json")
