"""Track browser-extension collection claims.

The claim fields make the overnight Amazon queue resumable and prevent two
extension slots from processing the same URL at the same time.
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260831_0023"
down_revision: str | None = "20260826_0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("collection_jobs", sa.Column("claimed_by", sa.String(length=120), nullable=True))
    op.add_column("collection_jobs", sa.Column("claimed_at", sa.DateTime(), nullable=True))
    op.create_index("ix_collection_jobs_claimed_by", "collection_jobs", ["claimed_by"])


def downgrade() -> None:
    op.drop_index("ix_collection_jobs_claimed_by", table_name="collection_jobs")
    op.drop_column("collection_jobs", "claimed_at")
    op.drop_column("collection_jobs", "claimed_by")
