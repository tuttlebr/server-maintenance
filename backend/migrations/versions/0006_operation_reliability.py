"""Track per-device access, execution ownership, and recovery.

Revision ID: 0006_operation_reliability
Revises: 0005_context_management
"""
import sqlalchemy as sa
from alembic import op

revision = "0006_operation_reliability"
down_revision = "0005_context_management"
branch_labels = None
depends_on = None


def upgrade():
    for column in (
        sa.Column("maintenance_mode", sa.String(), server_default="unknown"),
        sa.Column("kubernetes_context", sa.String()),
        sa.Column("kubernetes_node_name", sa.String()),
        sa.Column("facts_stale", sa.Boolean(), server_default=sa.true()),
        sa.Column("recovery_required", sa.Boolean(), server_default=sa.false()),
        sa.Column("recovery_reason", sa.Text()),
    ):
        op.add_column("hosts", column)
    # Existing global privilege flags are intentionally not copied to hosts.
    # A fresh observation is required before claiming a grant on a device.
    for column in (
        sa.Column("groups", sa.String()), sa.Column("shell", sa.String()),
        sa.Column("managed_sudo", sa.Boolean()), sa.Column("sudo_policy", sa.Text()),
        sa.Column("observed_at", sa.DateTime()),
        sa.Column("state", sa.String(), server_default="unverified"),
    ):
        op.add_column("user_host_assoc", column)
    for column in (
        sa.Column("execution_kind", sa.String(), server_default="unknown"),
        sa.Column("phase", sa.String(), server_default="queued"),
        sa.Column("outcomes_json", sa.Text(), server_default="[]"),
        sa.Column("request_key", sa.String()),
        sa.Column("request_fingerprint", sa.String()),
    ):
        op.add_column("jobs", column)
    op.create_index("ix_jobs_request_key", "jobs", ["request_key"], unique=True)
    op.create_table(
        "device_reservations",
        sa.Column("device_id", sa.Integer(), sa.ForeignKey("hosts.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("job_id", sa.String(), sa.ForeignKey("jobs.job_id", ondelete="CASCADE"), nullable=False),
    )


def downgrade():
    op.drop_table("device_reservations")
    op.drop_index("ix_jobs_request_key", table_name="jobs")
    for table, columns in (
        ("jobs", ("execution_kind", "phase", "outcomes_json", "request_key", "request_fingerprint")),
        ("user_host_assoc", ("groups", "shell", "managed_sudo", "sudo_policy", "observed_at", "state")),
        ("hosts", ("maintenance_mode", "kubernetes_context", "kubernetes_node_name", "facts_stale", "recovery_required", "recovery_reason")),
    ):
        for name in columns:
            op.drop_column(table, name)
