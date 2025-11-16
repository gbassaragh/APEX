"""Add unit cost fields to cost_codes

Revision ID: 20250115_add_cost_code_unit_costs
Revises: 20250115_add_background_jobs
Create Date: 2025-01-15
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20250115_add_cost_code_unit_costs"
down_revision = "20250115_add_background_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("cost_codes", sa.Column("unit_cost_material", sa.Numeric(15, 2), nullable=True))
    op.add_column("cost_codes", sa.Column("unit_cost_labor", sa.Numeric(15, 2), nullable=True))
    op.add_column("cost_codes", sa.Column("unit_cost_other", sa.Numeric(15, 2), nullable=True))
    op.add_column("cost_codes", sa.Column("unit_cost_total", sa.Numeric(15, 2), nullable=True))


def downgrade() -> None:
    op.drop_column("cost_codes", "unit_cost_total")
    op.drop_column("cost_codes", "unit_cost_other")
    op.drop_column("cost_codes", "unit_cost_labor")
    op.drop_column("cost_codes", "unit_cost_material")
