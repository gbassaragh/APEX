"""Add background_jobs table for async operations

Revision ID: 20250115_add_background_jobs
Revises: None
Create Date: 2025-01-15
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20250115_add_background_jobs"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "background_jobs",
        sa.Column("id", sa.CHAR(length=36), nullable=False),
        sa.Column("job_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("document_id", sa.CHAR(length=36), nullable=True),
        sa.Column("project_id", sa.CHAR(length=36), nullable=True),
        sa.Column("estimate_id", sa.CHAR(length=36), nullable=True),
        sa.Column("progress_percent", sa.Integer(), nullable=True),
        sa.Column("current_step", sa.String(length=255), nullable=True),
        sa.Column("result_data", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_by_id", sa.CHAR(length=36), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.ForeignKeyConstraint(["estimate_id"], ["estimates.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_background_jobs_status_created",
        "background_jobs",
        ["status", "created_at"],
    )
    op.create_index(op.f("ix_background_jobs_job_type"), "background_jobs", ["job_type"], unique=False)
    op.create_index(op.f("ix_background_jobs_status"), "background_jobs", ["status"], unique=False)
    op.create_index(op.f("ix_background_jobs_document_id"), "background_jobs", ["document_id"], unique=False)
    op.create_index(op.f("ix_background_jobs_project_id"), "background_jobs", ["project_id"], unique=False)
    op.create_index(op.f("ix_background_jobs_estimate_id"), "background_jobs", ["estimate_id"], unique=False)
    op.create_index(op.f("ix_background_jobs_created_at"), "background_jobs", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_background_jobs_created_at"), table_name="background_jobs")
    op.drop_index(op.f("ix_background_jobs_estimate_id"), table_name="background_jobs")
    op.drop_index(op.f("ix_background_jobs_project_id"), table_name="background_jobs")
    op.drop_index(op.f("ix_background_jobs_document_id"), table_name="background_jobs")
    op.drop_index(op.f("ix_background_jobs_status"), table_name="background_jobs")
    op.drop_index(op.f("ix_background_jobs_job_type"), table_name="background_jobs")
    op.drop_index("ix_background_jobs_status_created", table_name="background_jobs")
    op.drop_table("background_jobs")
