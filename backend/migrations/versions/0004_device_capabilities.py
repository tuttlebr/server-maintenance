"""add capability-driven device metadata

Revision ID: 0004_device_capabilities
Revises: 0003_remove_ai_job_analysis
Create Date: 2026-08-08
"""

import json

import sqlalchemy as sa
from alembic import op

revision = "0004_device_capabilities"
down_revision = "0003_remove_ai_job_analysis"
branch_labels = None
depends_on = None


LEGACY_KIND = {
    "dgx_spark": "edge",
    "dgx_workstation": "workstation",
    "cpu_node": "server",
    "gpu_node": "server",
    "unknown": "generic",
}

LEGACY_CAPABILITIES = {
    "dgx_spark": [
        "system.scan", "system.reboot", "system.update", "storage.inspect",
        "containers.cleanup", "users.manage", "gpu.inspect", "nvidia.driver.manage",
    ],
    "dgx_workstation": [
        "system.scan", "system.reboot", "system.update", "storage.inspect",
        "containers.cleanup", "users.manage", "gpu.inspect", "nvidia.driver.manage",
        "nvidia.fabric_manager.manage", "nvidia.mig.manage", "kubernetes.drain",
    ],
    "cpu_node": [
        "system.scan", "system.reboot", "system.update", "storage.inspect",
        "containers.cleanup", "users.manage", "kubernetes.drain",
    ],
    "gpu_node": [
        "system.scan", "system.reboot", "system.update", "storage.inspect",
        "containers.cleanup", "users.manage", "gpu.inspect", "nvidia.driver.manage",
        "kubernetes.drain",
    ],
    "unknown": ["system.scan", "system.reboot", "storage.inspect", "users.manage"],
}


def upgrade() -> None:
    columns = (
        sa.Column("display_name", sa.String(), nullable=True),
        sa.Column("kind", sa.String(), nullable=True),
        sa.Column("vendor", sa.String(), nullable=True),
        sa.Column("model", sa.String(), nullable=True),
        sa.Column("architecture", sa.String(), nullable=True),
        sa.Column("os_family", sa.String(), nullable=True),
        sa.Column("transport", sa.String(), nullable=True),
        sa.Column("endpoint", sa.String(), nullable=True),
        sa.Column("daemon_port", sa.Integer(), nullable=True),
        sa.Column("capabilities_json", sa.Text(), nullable=True),
        sa.Column("facts_json", sa.Text(), nullable=True),
        sa.Column("discovered_at", sa.DateTime(), nullable=True),
    )
    for column in columns:
        op.add_column("hosts", column)

    connection = op.get_bind()
    rows = connection.execute(sa.text("SELECT id, hostname, ip_address, machine_type FROM hosts")).mappings()
    for row in rows:
        legacy = row["machine_type"] if row["machine_type"] in LEGACY_KIND else "unknown"
        vendor = "NVIDIA" if legacy.startswith("dgx_") or legacy == "gpu_node" else None
        connection.execute(
            sa.text(
                """UPDATE hosts SET display_name=:display_name, kind=:kind, vendor=:vendor,
                transport='ssh', endpoint=:endpoint, capabilities_json=:capabilities,
                facts_json='{}' WHERE id=:id"""
            ),
            {
                "id": row["id"],
                "display_name": row["hostname"],
                "kind": LEGACY_KIND[legacy],
                "vendor": vendor,
                "endpoint": row["ip_address"] or row["hostname"],
                "capabilities": json.dumps(LEGACY_CAPABILITIES[legacy]),
            },
        )


def downgrade() -> None:
    for column in (
        "discovered_at", "facts_json", "capabilities_json", "daemon_port", "endpoint",
        "transport", "os_family", "architecture", "model", "vendor", "kind", "display_name",
    ):
        op.drop_column("hosts", column)
