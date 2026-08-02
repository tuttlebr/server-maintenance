"""add persistent login throttles

Revision ID: 0002_login_throttles
Revises: 0001_initial
Create Date: 2026-07-21
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_login_throttles"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "login_throttles",
        sa.Column("key", sa.String(length=80), nullable=False),
        sa.Column("window_started_at", sa.Integer(), nullable=False),
        sa.Column("failure_count", sa.Integer(), nullable=False),
        sa.Column("blocked_until", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )


def downgrade() -> None:
    op.drop_table("login_throttles")
