"""add context documents and device annotations

Revision ID: 0005_context_management
Revises: 0004_device_capabilities
Create Date: 2026-08-09
"""

import sqlalchemy as sa
from alembic import op

revision = "0005_context_management"
down_revision = "0004_device_capabilities"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("hosts", sa.Column("annotations_json", sa.Text(), nullable=True))
    op.execute("UPDATE hosts SET annotations_json='{}' WHERE annotations_json IS NULL")
    op.create_table(
        "context_documents",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=80), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=True),
        sa.Column("uploaded_by", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["hosts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_context_documents_device_id"), "context_documents", ["device_id"])
    op.create_index(op.f("ix_context_documents_sha256"), "context_documents", ["sha256"])


def downgrade() -> None:
    op.drop_index(op.f("ix_context_documents_sha256"), table_name="context_documents")
    op.drop_index(op.f("ix_context_documents_device_id"), table_name="context_documents")
    op.drop_table("context_documents")
    op.drop_column("hosts", "annotations_json")
