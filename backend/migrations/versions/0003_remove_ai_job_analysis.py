"""remove external AI job analysis storage

Revision ID: 0003_remove_ai_job_analysis
Revises: 0002_login_throttles
Create Date: 2026-07-21
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_remove_ai_job_analysis"
down_revision = "0002_login_throttles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("jobs") as batch_op:
        batch_op.drop_column("ai_analysis")


def downgrade() -> None:
    with op.batch_alter_table("jobs") as batch_op:
        batch_op.add_column(sa.Column("ai_analysis", sa.Text(), nullable=True))
