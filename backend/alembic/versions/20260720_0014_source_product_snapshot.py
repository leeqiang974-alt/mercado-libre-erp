"""persist structured Amazon source snapshots

Revision ID: 20260720_0014
Revises: 20260720_0013
Create Date: 2026-07-20
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260720_0014"
down_revision: str | None = "20260720_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("source_products") as batch_op:
        batch_op.add_column(
            sa.Column(
                "collection_method",
                sa.String(length=40),
                nullable=False,
                server_default="browser_page",
            )
        )
        batch_op.add_column(sa.Column("title", sa.Text(), nullable=False, server_default=""))
        batch_op.add_column(sa.Column("brand", sa.Text(), nullable=False, server_default=""))
        batch_op.add_column(sa.Column("source_price", sa.Float(), nullable=True))
        batch_op.add_column(
            sa.Column("source_currency", sa.String(length=8), nullable=False, server_default="")
        )
        batch_op.add_column(sa.Column("description", sa.Text(), nullable=False, server_default=""))
        batch_op.add_column(
            sa.Column("bullets_json", sa.JSON(), nullable=False, server_default="[]")
        )
        batch_op.add_column(
            sa.Column("image_urls_json", sa.JSON(), nullable=False, server_default="[]")
        )
        batch_op.add_column(
            sa.Column("variants_json", sa.JSON(), nullable=False, server_default="[]")
        )
        batch_op.add_column(
            sa.Column("technical_details_json", sa.JSON(), nullable=False, server_default="{}")
        )
def downgrade() -> None:
    with op.batch_alter_table("source_products") as batch_op:
        batch_op.drop_column("technical_details_json")
        batch_op.drop_column("variants_json")
        batch_op.drop_column("image_urls_json")
        batch_op.drop_column("bullets_json")
        batch_op.drop_column("description")
        batch_op.drop_column("source_currency")
        batch_op.drop_column("source_price")
        batch_op.drop_column("brand")
        batch_op.drop_column("title")
        batch_op.drop_column("collection_method")
