"""product draft approvals

Revision ID: 20260707_0005
Revises: 20260707_0004
Create Date: 2026-07-07
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260707_0005"
down_revision: str | None = "20260707_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "product_draft_approvals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_draft_id", sa.Integer(), sa.ForeignKey("product_drafts.id"), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("approved_by", sa.String(length=120), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("approved_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_product_draft_approvals_product_draft_id",
        "product_draft_approvals",
        ["product_draft_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_product_draft_approvals_product_draft_id",
        table_name="product_draft_approvals",
    )
    op.drop_table("product_draft_approvals")
