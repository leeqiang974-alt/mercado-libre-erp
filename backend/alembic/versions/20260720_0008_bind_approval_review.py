"""bind approvals to the exact behavioral review

Revision ID: 20260720_0008
Revises: 20260716_0007
Create Date: 2026-07-20
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260720_0008"
down_revision: str | None = "20260716_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "product_draft_approvals",
        sa.Column("review_result_id", sa.Integer(), nullable=True),
    )
    with op.batch_alter_table("product_draft_approvals") as batch_op:
        batch_op.create_foreign_key(
            "fk_product_draft_approvals_review_result_id",
            "review_results",
            ["review_result_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("product_draft_approvals") as batch_op:
        batch_op.drop_constraint(
            "fk_product_draft_approvals_review_result_id",
            type_="foreignkey",
        )
    op.drop_column("product_draft_approvals", "review_result_id")
