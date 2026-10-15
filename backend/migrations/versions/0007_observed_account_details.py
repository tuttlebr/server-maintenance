"""Keep account details observed on each device.

Revision ID: 0007_observed_account_details
Revises: 0006_operation_reliability
"""
import sqlalchemy as sa
from alembic import op

revision = "0007_observed_account_details"
down_revision = "0006_operation_reliability"
branch_labels = None
depends_on = None


def upgrade():
    for column in (
        sa.Column("full_name", sa.String()),
        sa.Column("uid", sa.Integer()),
        sa.Column("home", sa.String()),
    ):
        op.add_column("user_host_assoc", column)


def downgrade():
    for name in ("home", "uid", "full_name"):
        op.drop_column("user_host_assoc", name)
