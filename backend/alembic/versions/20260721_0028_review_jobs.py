"""add queued combined review jobs

Revision ID: 20260721_0028
Revises: 20260721_0027
Create Date: 2026-07-21
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260721_0028"
down_revision: str | None = "20260721_0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "review_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("batch_id", sa.String(length=36), nullable=False),
        sa.Column("product_draft_id", sa.Integer(), nullable=False),
        sa.Column("requested_by", sa.String(length=120), nullable=False),
        sa.Column("draft_version", sa.Integer(), nullable=False),
        sa.Column("baseline_review_result_id", sa.Integer(), nullable=True),
        sa.Column("active_key", sa.String(length=80), nullable=True),
        sa.Column("status", sa.Enum("PENDING", "RUNNING", "COMPLETED", "BLOCKED", "FAILED", name="reviewjobstatus"), nullable=False),
        sa.Column("aggregate_review_result_id", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(length=160), nullable=False),
        sa.Column("error_detail_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["aggregate_review_result_id"], ["review_results.id"]),
        sa.ForeignKeyConstraint(["baseline_review_result_id"], ["review_results.id"]),
        sa.ForeignKeyConstraint(["product_draft_id"], ["product_drafts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_review_jobs_batch_id", "review_jobs", ["batch_id"])
    op.create_index("ix_review_jobs_product_draft_id", "review_jobs", ["product_draft_id"])
    op.create_index("uq_review_jobs_active_key", "review_jobs", ["active_key"], unique=True)
    with op.batch_alter_table("review_results") as batch_op:
        batch_op.add_column(sa.Column("review_job_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_review_results_review_job_id",
            "review_jobs",
            ["review_job_id"],
            ["id"],
        )
        batch_op.create_index("ix_review_results_review_job_id", ["review_job_id"])


def downgrade() -> None:
    bind = op.get_bind()
    review_result_columns = {
        column["name"] for column in sa.inspect(bind).get_columns("review_results")
    }
    if "review_job_id" in review_result_columns:
        with op.batch_alter_table("review_results") as batch_op:
            batch_op.drop_index("ix_review_results_review_job_id")
            batch_op.drop_constraint(
                "fk_review_results_review_job_id", type_="foreignkey"
            )
            batch_op.drop_column("review_job_id")
    op.drop_index("uq_review_jobs_active_key", table_name="review_jobs")
    op.drop_index("ix_review_jobs_product_draft_id", table_name="review_jobs")
    op.drop_index("ix_review_jobs_batch_id", table_name="review_jobs")
    op.drop_table("review_jobs")
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS reviewjobstatus")
