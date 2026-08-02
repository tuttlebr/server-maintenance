"""initial fleet manager schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-20
"""

from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hosts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("hostname", sa.String(), nullable=False),
        sa.Column("ip_address", sa.String(), nullable=True),
        sa.Column("machine_type", sa.String(), nullable=True),
        sa.Column("ansible_user", sa.String(), nullable=True),
        sa.Column("ansible_password", sa.String(), nullable=True),
        sa.Column("ansible_become_password", sa.String(), nullable=True),
        sa.Column("os_version", sa.String(), nullable=True),
        sa.Column("gpu_model", sa.String(), nullable=True),
        sa.Column("driver_version", sa.String(), nullable=True),
        sa.Column("cuda_version", sa.String(), nullable=True),
        sa.Column("memory_gb", sa.Integer(), nullable=True),
        sa.Column("nic_type", sa.String(), nullable=True),
        sa.Column("nic_speed", sa.String(), nullable=True),
        sa.Column("fabric_manager_status", sa.String(), nullable=True),
        sa.Column("disk_root_percent", sa.Integer(), nullable=True),
        sa.Column("disk_raid_percent", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("reboot_required", sa.Boolean(), nullable=True),
        sa.Column("last_seen", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_hosts_hostname"), "hosts", ["hostname"], unique=True)

    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.String(), nullable=False),
        sa.Column("playbook", sa.String(), nullable=False),
        sa.Column("target_hosts", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("triggered_by", sa.String(), nullable=True),
        sa.Column("extra_vars", sa.Text(), nullable=True),
        sa.Column("output_log", sa.Text(), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("recap", sa.Text(), nullable=True),
        sa.Column("ai_analysis", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_jobs_job_id"), "jobs", ["job_id"], unique=True)

    op.create_table(
        "managed_users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(), nullable=False),
        sa.Column("full_name", sa.String(), nullable=True),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("is_sudoer", sa.Boolean(), nullable=True),
        sa.Column("groups", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_managed_users_username"), "managed_users", ["username"], unique=False)

    op.create_table(
        "user_host_assoc",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("host_id", sa.Integer(), nullable=False),
        sa.Column("provisioned_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["host_id"], ["hosts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["managed_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "host_id"),
    )


def downgrade() -> None:
    op.drop_table("user_host_assoc")
    op.drop_index(op.f("ix_managed_users_username"), table_name="managed_users")
    op.drop_table("managed_users")
    op.drop_index(op.f("ix_jobs_job_id"), table_name="jobs")
    op.drop_table("jobs")
    op.drop_index(op.f("ix_hosts_hostname"), table_name="hosts")
    op.drop_table("hosts")
